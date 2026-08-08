from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api import services


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

    return app


def _get_analyzer():
    return services.get_analyzer()


app = create_app()
