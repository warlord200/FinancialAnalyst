import time
from pathlib import Path

from financial_analyst.jobs import (
    InlineJobRunner,
    JobStore,
    MAX_ATTEMPTS,
    PollingWorker,
    QueueJobRunner,
    ThreadJobRunner,
)


def test_job_store_round_trip_and_update(tmp_path):
    store = JobStore(str(tmp_path / "jobs.db"))
    job = store.create("TSLA")
    assert job["status"] == "queued"
    assert store.get(job["id"])["id"] == job["id"]

    updated = store.update(job["id"], status="running", progress=50)
    assert updated["status"] == "running"
    assert updated["progress"] == 50

    assert store.get("nope") is None

    reloaded = JobStore(str(tmp_path / "jobs.db"))
    assert reloaded.get(job["id"])["status"] == "running"


def test_inline_runner_completes_job(tmp_path):
    store = JobStore(str(tmp_path / "jobs.db"))
    job = store.create("TSLA")
    InlineJobRunner().run(store, job["id"], lambda: {"num_chunks": 12})

    done = store.get(job["id"])
    assert done["status"] == "completed"
    assert done["progress"] == 100
    assert done["result"] == {"num_chunks": 12}


def test_inline_runner_records_failure(tmp_path):
    store = JobStore(str(tmp_path / "jobs.db"))
    job = store.create("TSLA")

    def boom():
        raise ValueError("bad filing")

    InlineJobRunner().run(store, job["id"], boom)

    done = store.get(job["id"])
    assert done["status"] == "failed"
    assert "bad filing" in done["error"]


def test_thread_runner_completes_job(tmp_path):
    store = JobStore(str(tmp_path / "jobs.db"))
    job = store.create("TSLA")
    ThreadJobRunner().run(store, job["id"], lambda: {"num_chunks": 7})

    deadline = time.time() + 10
    while time.time() < deadline:
        if store.get(job["id"])["status"] == "completed":
            break
        time.sleep(0.05)
    done = store.get(job["id"])
    assert done["status"] == "completed"
    assert done["result"] == {"num_chunks": 7}


def test_job_store_persists_to_disk(tmp_path):
    path = str(tmp_path / "sub" / "jobs.db")
    store = JobStore(path)
    job = store.create("AAPL")
    assert Path(path).is_file()
    store.update(job["id"], status="completed")
    assert JobStore(path).get(job["id"])["status"] == "completed"


def test_two_store_instances_share_the_table(tmp_path):
    """The job store must be safe across processes: an API process and the
    worker process each hold their own JobStore over the same SQLite file."""
    first = JobStore(str(tmp_path / "jobs.db"))
    second = JobStore(str(tmp_path / "jobs.db"))
    job = first.create("TSLA")
    assert second.get(job["id"])["status"] == "queued"
    second.update(job["id"], progress=40)
    assert first.get(job["id"])["progress"] == 40


def test_claim_next_returns_oldest_queued_job_as_running(tmp_path):
    store = JobStore(str(tmp_path / "jobs.db"))
    older = store.create("TSLA")
    newer = store.create("AAPL")

    claimed = store.claim_next()
    assert claimed["id"] == older["id"]
    assert claimed["status"] == "running"

    second = store.claim_next()
    assert second["id"] == newer["id"]
    assert store.get(newer["id"])["status"] == "running"

    assert store.claim_next() is None


def test_claim_next_increments_attempts(tmp_path):
    store = JobStore(str(tmp_path / "jobs.db"))
    job = store.create("TSLA")
    assert job["attempts"] == 0

    first = store.claim_next()
    assert first["attempts"] == 1
    store.requeue_stale()

    second = store.claim_next()
    assert second["attempts"] == 2
    assert store.get(job["id"])["attempts"] == 2


def test_claim_next_only_claims_queued_jobs(tmp_path):
    store = JobStore(str(tmp_path / "jobs.db"))
    running = store.create("TSLA")
    store.update(running["id"], status="running")
    queued = store.create("AAPL")

    assert store.claim_next()["id"] == queued["id"]
    assert store.claim_next() is None


def test_requeue_stale_leaves_failed_jobs_alone(tmp_path):
    store = JobStore(str(tmp_path / "jobs.db"))
    job = store.create("TSLA")
    store.update(job["id"], status="running", progress=30)
    store.update(job["id"], status="failed")

    store.requeue_stale()
    assert store.get(job["id"])["status"] == "failed"


def test_requeue_stale_returns_running_jobs_to_queued(tmp_path):
    """After a worker restart, jobs that were mid-flight must run again."""
    store = JobStore(str(tmp_path / "jobs.db"))
    job = store.create("TSLA")
    store.update(job["id"], status="running", progress=30)
    store.requeue_stale()
    assert store.get(job["id"])["status"] == "queued"


def test_requeue_stale_fails_a_poison_job_after_max_attempts(tmp_path):
    """A job whose worker keeps crashing must not be requeued forever."""
    store = JobStore(str(tmp_path / "jobs.db"))
    job = store.create("TSLA")

    for _ in range(MAX_ATTEMPTS):
        store.claim_next()
        store.requeue_stale()

    done = store.get(job["id"])
    assert done["status"] == "failed"
    assert "worker attempts" in done["error"]


def test_requeue_stale_requeues_while_attempts_remain(tmp_path):
    store = JobStore(str(tmp_path / "jobs.db"))
    job = store.create("TSLA")
    store.claim_next()  # attempts -> 1

    store.requeue_stale()
    assert store.get(job["id"])["status"] == "queued"


def test_queue_runner_leaves_the_job_for_the_worker(tmp_path):
    store = JobStore(str(tmp_path / "jobs.db"))
    job = store.create("TSLA")
    QueueJobRunner().run(store, job["id"], lambda: {"num_chunks": 5})
    assert store.get(job["id"])["status"] == "queued"


class TestPollingWorker:
    def test_process_once_completes_a_claimed_job(self, tmp_path):
        store = JobStore(str(tmp_path / "jobs.db"))
        job = store.create("TSLA")
        worker = PollingWorker(store, lambda claimed: {"num_chunks": 9})

        assert worker.process_once() is True
        done = store.get(job["id"])
        assert done["status"] == "completed"
        assert done["progress"] == 100
        assert done["result"] == {"num_chunks": 9}

    def test_process_once_records_failure(self, tmp_path):
        store = JobStore(str(tmp_path / "jobs.db"))
        job = store.create("TSLA")

        def boom(claimed):
            raise ValueError("SEC EDGAR unavailable")

        worker = PollingWorker(store, boom)
        assert worker.process_once() is True
        done = store.get(job["id"])
        assert done["status"] == "failed"
        assert "SEC EDGAR unavailable" in done["error"]

    def test_process_once_returns_false_when_idle(self, tmp_path):
        store = JobStore(str(tmp_path / "jobs.db"))
        worker = PollingWorker(store, lambda claimed: {})
        assert worker.process_once() is False

    def test_worker_start_requeues_orphaned_running_jobs(self, tmp_path):
        store = JobStore(str(tmp_path / "jobs.db"))
        job = store.create("TSLA")
        store.update(job["id"], status="running", progress=30)

        worker = PollingWorker(store, lambda claimed: {"num_chunks": 2})
        assert worker.process_once() is True
        assert store.get(job["id"])["status"] == "completed"

    def test_worker_processes_all_queued_jobs_in_order(self, tmp_path):
        store = JobStore(str(tmp_path / "jobs.db"))
        store.create("TSLA")
        store.create("AAPL")
        seen = []
        worker = PollingWorker(store, lambda claimed: seen.append(claimed["ticker"]) or {})

        assert worker.process_once() is True
        assert worker.process_once() is True
        assert worker.process_once() is False
        assert seen == ["TSLA", "AAPL"]
