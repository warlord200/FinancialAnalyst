import time
from pathlib import Path

from financial_analyst.jobs import InlineJobRunner, JobStore, ThreadJobRunner


def test_job_store_round_trip_and_update(tmp_path):
    store = JobStore(str(tmp_path / "jobs.json"))
    job = store.create("TSLA")
    assert job["status"] == "queued"
    assert store.get(job["id"])["id"] == job["id"]

    updated = store.update(job["id"], status="running", progress=50)
    assert updated["status"] == "running"
    assert updated["progress"] == 50

    assert store.get("nope") is None

    reloaded = JobStore(str(tmp_path / "jobs.json"))
    assert reloaded.get(job["id"])["status"] == "running"


def test_inline_runner_completes_job(tmp_path):
    store = JobStore(str(tmp_path / "jobs.json"))
    job = store.create("TSLA")
    InlineJobRunner().run(store, job["id"], lambda: {"num_chunks": 12})

    done = store.get(job["id"])
    assert done["status"] == "completed"
    assert done["progress"] == 100
    assert done["result"] == {"num_chunks": 12}


def test_inline_runner_records_failure(tmp_path):
    store = JobStore(str(tmp_path / "jobs.json"))
    job = store.create("TSLA")

    def boom():
        raise ValueError("bad filing")

    InlineJobRunner().run(store, job["id"], boom)

    done = store.get(job["id"])
    assert done["status"] == "failed"
    assert "bad filing" in done["error"]


def test_thread_runner_completes_job(tmp_path):
    store = JobStore(str(tmp_path / "jobs.json"))
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
    path = str(tmp_path / "sub" / "jobs.json")
    store = JobStore(path)
    job = store.create("AAPL")
    assert Path(path).is_file()
    store.update(job["id"], status="completed")
    assert JobStore(path).get(job["id"])["status"] == "completed"
