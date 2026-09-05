"""Durable job store (SQLite) and the job runners.

The deployment runs the API and the background worker as separate
processes, so the job table lives in SQLite (cross-process safe) rather
than a JSON file: the API enqueues a job and the worker claims and runs
it, and both read the same table. In single-process local use and in
tests, the job runner executes the work inline or in a daemon thread
instead.

A job is one ticker ingestion (download, chunk, index). ``JobStore`` is a
thin SQLite table with a dict-shaped job contract
(``id, ticker, status, progress, attempts, created_at, updated_at, result,
error``); the runners differ only in where the work executes. ``attempts``
counts worker claims, so a job whose worker keeps crashing is failed after
``MAX_ATTEMPTS`` rather than requeued forever.
"""

import json
import threading
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone

from financial_analyst.storage.sqlite import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    result TEXT,
    error TEXT
);
"""

QUEUED = "queued"
RUNNING = "running"
COMPLETED = "completed"
FAILED = "failed"

# A job whose worker keeps crashing is requeued up to this many times, then
# marked failed instead of retrying forever (systemd restarts the worker, so
# an unbounded requeue would spin on a poison job indefinitely).
MAX_ATTEMPTS = 3

_UPDATEABLE = ("status", "progress", "result", "error")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    """Per-ticker background jobs, backed by SQLite for cross-process use.

    A job is created ``queued``; the API process (in worker mode) leaves
    it that way and the worker process claims it via ``claim_next``. Two
    JobStore instances over the same path are separate handles on the same
    table, which is what lets the API and the worker share state.
    """

    def __init__(self, path: str = "./storage/jobs.db") -> None:
        self.path = path
        with closing(connect(path, SCHEMA)) as conn:
            self._migrate(conn)

    @staticmethod
    def _migrate(conn) -> None:
        """Add the ``attempts`` column to tables created before it existed."""
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
        if "attempts" not in columns:
            conn.execute(
                "ALTER TABLE jobs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0"
            )
            conn.commit()

    @staticmethod
    def _from_row(row: dict | None) -> dict | None:
        if row is None:
            return None
        job = dict(row)
        if job.get("result") is not None:
            job["result"] = json.loads(job["result"])
        return job

    def create(self, ticker: str) -> dict:
        now = _now()
        job_id = uuid.uuid4().hex
        with closing(connect(self.path, SCHEMA)) as conn:
            conn.execute(
                "INSERT INTO jobs"
                " (id, ticker, status, progress, created_at, updated_at, result, error)"
                " VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
                (job_id, ticker.upper(), QUEUED, 0, now, now),
            )
            conn.commit()
        return {
            "id": job_id,
            "ticker": ticker.upper(),
            "status": QUEUED,
            "progress": 0,
            "attempts": 0,
            "created_at": now,
            "updated_at": now,
            "result": None,
            "error": None,
        }

    def get(self, job_id: str) -> dict | None:
        with closing(connect(self.path, SCHEMA)) as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._from_row(row)

    def update(self, job_id: str, **fields) -> dict | None:
        """Update a job's mutable fields and return the fresh job row.

        ``result`` is JSON-serialised on write and parsed back on read.
        """
        invalid = [key for key in fields if key not in _UPDATEABLE]
        if invalid:
            raise ValueError(f"Unknown job fields: {', '.join(invalid)}")
        if not fields:
            return self.get(job_id)
        assignments = []
        values = []
        for key, value in fields.items():
            if key == "result" and value is not None:
                value = json.dumps(value)
            assignments.append(f"{key} = ?")
            values.append(value)
        assignments.append("updated_at = ?")
        values.append(_now())
        values.append(job_id)
        with closing(connect(self.path, SCHEMA)) as conn:
            conn.execute(
                f"UPDATE jobs SET {', '.join(assignments)} WHERE id = ?", values
            )
            conn.commit()
        return self.get(job_id)

    def claim_next(self) -> dict | None:
        """Atomically claim the oldest queued job and mark it running.

        Returns the claimed job (``status="running"``) or None when nothing
        is queued. The claim is atomic so two worker processes never pick
        up the same job. Each claim bumps ``attempts``; a worker that keeps
        crashing on the same job is eventually failed (see
        ``requeue_stale``) instead of being retried forever.
        """
        with closing(connect(self.path, SCHEMA)) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT * FROM jobs WHERE status = ?"
                    " ORDER BY created_at, rowid LIMIT 1",
                    (QUEUED,),
                ).fetchone()
                if row is None:
                    conn.rollback()
                    return None
                conn.execute(
                    "UPDATE jobs SET status = ?, attempts = attempts + 1,"
                    " updated_at = ? WHERE id = ?",
                    (RUNNING, _now(), row["id"]),
                )
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        return self.get(row["id"])

    def requeue_stale(self) -> int:
        """Return jobs left ``running`` to ``queued`` (crash recovery).

        When the worker process dies mid-job, its job is stuck ``running``;
        the next worker start requeues it so the ingest runs again. A job
        claimed ``MAX_ATTEMPTS`` times without completing is instead marked
        ``failed``, so a job that keeps killing the worker does not spin
        forever under ``systemd Restart=always``. Returns the number of jobs
        requeued.
        """
        with closing(connect(self.path, SCHEMA)) as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, error = ?, updated_at = ?"
                " WHERE status = ? AND attempts >= ?",
                (
                    FAILED,
                    f"job failed after {MAX_ATTEMPTS} worker attempts",
                    _now(),
                    RUNNING,
                    MAX_ATTEMPTS,
                ),
            )
            cursor = conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ?"
                " WHERE status = ? AND attempts < ?",
                (QUEUED, _now(), RUNNING, MAX_ATTEMPTS),
            )
            conn.commit()
        return cursor.rowcount


def _complete(store: JobStore, job_id: str, fn) -> None:
    """Run ``fn`` and record the outcome on the job: completed on success,
    failed with the exception text on error."""
    try:
        result = fn()
        store.update(job_id, status=COMPLETED, progress=100, result=result)
    except Exception as exc:
        store.update(job_id, status=FAILED, error=str(exc))


class JobRunner:
    def run(self, store: JobStore, job_id: str, fn) -> None:
        _complete(store, job_id, fn)


class InlineJobRunner(JobRunner):
    pass


class ThreadJobRunner(JobRunner):
    def run(self, store: JobStore, job_id: str, fn) -> None:
        def _worker() -> None:
            store.update(job_id, status=RUNNING, progress=10)
            JobRunner.run(self, store, job_id, fn)

        threading.Thread(target=_worker, daemon=True).start()


class QueueJobRunner(JobRunner):
    """Enqueue-only runner for the API process in worker mode.

    ``run`` deliberately does nothing: the job was already created
    ``queued``, and the separate worker process claims and executes it.
    """

    def run(self, store: JobStore, job_id: str, fn) -> None:
        return None


class PollingWorker:
    """Claims and runs queued jobs one at a time.

    ``run_job`` is called with the claimed job dict and must return the
    job's result dict, or raise for the job to be marked failed. On
    construction the worker requeues any ``running`` job left by a
    previous, now-dead worker, so an interrupted ingest runs again after a
    restart.
    """

    def __init__(self, store: JobStore, run_job, requeue_stale_on_start: bool = True) -> None:
        self.store = store
        self.run_job = run_job
        if requeue_stale_on_start:
            self.store.requeue_stale()

    def process_once(self) -> bool:
        """Claim and run one queued job. Returns False when the queue is idle."""
        job = self.store.claim_next()
        if job is None:
            return False
        _complete(self.store, job["id"], lambda: self.run_job(job))
        return True

    def run_forever(self, poll_seconds: float = 1.0) -> None:
        while True:
            if not self.process_once():
                time.sleep(poll_seconds)
