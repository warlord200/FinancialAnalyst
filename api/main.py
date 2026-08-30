from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api import services
from financial_analyst.ingestion.sec_downloader import (
    SECDownloadError,
    TickerNotFoundError,
)
from financial_analyst.numbers.xbrl import XBRLEdgarError


class PriceOverride(BaseModel):
    price: float


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

    @app.post("/api/numbers/{ticker}/refresh")
    def refresh_numbers(ticker: str):
        ticker = ticker.upper()
        try:
            return _get_numbers_service().refresh(ticker)
        except TickerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except XBRLEdgarError:
            raise HTTPException(status_code=503, detail="SEC EDGAR unavailable, try again later")

    @app.get("/api/numbers/{ticker}")
    def get_numbers(ticker: str):
        ticker = ticker.upper()
        numbers = _get_numbers_service().get(ticker)
        if numbers is None:
            raise HTTPException(
                status_code=404, detail=f"No numbers found for {ticker}; refresh first"
            )
        return numbers

    @app.put("/api/numbers/{ticker}/price")
    def set_price_override(ticker: str, override: PriceOverride):
        ticker = ticker.upper()
        return _get_numbers_service().set_price_override(ticker, override.price)

    @app.delete("/api/numbers/{ticker}/price")
    def clear_price_override(ticker: str):
        ticker = ticker.upper()
        return _get_numbers_service().clear_price_override(ticker)

    return app


def _get_ingest_service():
    return services.get_ingest_service()


def _get_numbers_service():
    return services.get_numbers_service()


def _get_analyzer():
    return services.get_analyzer()


app = create_app()
