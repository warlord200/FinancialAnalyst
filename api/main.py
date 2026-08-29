from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api import services
from financial_analyst.ingestion.sec_downloader import (
    SECDownloadError,
    TickerNotFoundError,
)


def create_app() -> FastAPI:
    app = FastAPI(title="10-K Financial Analyst")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/api/analyze/{ticker}")
    def analyze(ticker: str):
        ticker = ticker.upper()
        return _get_analyzer().analyze(ticker)

    @app.get("/api/report/{ticker}")
    def get_report(ticker: str):
        ticker = ticker.upper()
        report = _get_analyzer().get_report(ticker)
        if report is None:
            raise HTTPException(status_code=404, detail=f"No report found for {ticker}")
        return report

    @app.get("/api/tickers")
    def list_tickers():
        return _get_analyzer().list_tickers()

    @app.post("/api/reanalyze/{ticker}")
    def reanalyze(ticker: str):
        ticker = ticker.upper()
        return _get_analyzer().reanalyze(ticker)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/ingest/{ticker}")
    def ingest(ticker: str):
        ticker = ticker.upper()
        try:
            return _get_ingest_service().ingest(ticker)
        except TickerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except SECDownloadError:
            raise HTTPException(status_code=503, detail="SEC EDGAR unavailable, try again later")

    @app.get("/api/ingest/jobs/{job_id}")
    def get_job(job_id: str):
        job = _get_ingest_service().get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"No job found: {job_id}")
        return job

    @app.get("/api/ingest")
    def list_ingested():
        return _get_ingest_service().list_ingested()

    @app.get("/api/ingest/{ticker}/stats")
    def get_ingest_stats(ticker: str):
        ticker = ticker.upper()
        stats = _get_ingest_service().get_stats(ticker)
        if stats is None:
            raise HTTPException(status_code=404, detail=f"Not ingested: {ticker}")
        return stats

    return app


def _get_ingest_service():
    return services.get_ingest_service()


def _get_analyzer():
    return services.get_analyzer()


app = create_app()
