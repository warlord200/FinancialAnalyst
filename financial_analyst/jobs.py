import threading
import uuid
from datetime import datetime, timezone

from financial_analyst.storage.json_store import JsonFileStore


class JobStore(JsonFileStore):
    def __init__(self, path: str = "./storage/jobs.json") -> None:
        super().__init__(path)

    def create(self, ticker: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        job = {
            "id": uuid.uuid4().hex,
            "ticker": ticker.upper(),
            "status": "queued",
            "progress": 0,
            "created_at": now,
            "updated_at": now,
            "result": None,
            "error": None,
        }
        self.set(job["id"], job)
        return dict(job)

    def update(self, job_id: str, **fields) -> dict:
        with self._lock:
            job = self._data[job_id]
            job.update(fields)
            job["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save()
            return dict(job)


class JobRunner:
    def run(self, store: JobStore, job_id: str, fn) -> None:
        try:
            result = fn()
            store.update(job_id, status="completed", progress=100, result=result)
        except Exception as exc:
            store.update(job_id, status="failed", error=str(exc))


class InlineJobRunner(JobRunner):
    pass


class ThreadJobRunner(JobRunner):
    def run(self, store: JobStore, job_id: str, fn) -> None:
        def _worker() -> None:
            store.update(job_id, status="running", progress=10)
            JobRunner.run(self, store, job_id, fn)

        threading.Thread(target=_worker, daemon=True).start()
