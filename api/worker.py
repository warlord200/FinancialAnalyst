"""The background worker process.

The deployment runs two processes on the box: the FastAPI app
(``api.main:app``) and this worker. The worker owns the long-running work
— the per-ticker ingest pipeline (SEC download, parse, chunk, embed,
index) — which the API only enqueues when ``JOB_RUNNER=worker``. Jobs live
in a shared SQLite table, so a worker restart requeues any job that was
mid-flight and it runs again.

Run with::

    python -m api.worker
"""

import logging
import os

from api.services import get_ingest_service
from financial_analyst.jobs import PollingWorker

logger = logging.getLogger(__name__)


def run_forever() -> None:
    service = get_ingest_service()
    worker = PollingWorker(service.job_store, service.run_job)
    logger.info("worker ready; polling %s for queued jobs", service.job_store.path)
    worker.run_forever()


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run_forever()


if __name__ == "__main__":
    main()
