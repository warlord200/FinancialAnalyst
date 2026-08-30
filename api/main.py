from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api import services
from financial_analyst.auth.quota import RESOURCE_ANALYSES, QuotaExceededError
from financial_analyst.auth.users import (
    InvalidCredentialsError,
    InvalidEmailError,
    UserAlreadyExistsError,
    WeakPasswordError,
)
from financial_analyst.ingestion.sec_downloader import (
    SECDownloadError,
    TickerNotFoundError,
)
from financial_analyst.numbers.xbrl import XBRLEdgarError


class PriceOverride(BaseModel):
    price: float


class AuthRequest(BaseModel):
    email: str
    password: str


def get_current_user(request: Request) -> dict:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = _get_auth_service().authenticate_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


def require_quota(resource: str):
    def dependency(user: dict = Depends(get_current_user)) -> dict:
        try:
            return _get_quota_service().consume(user, resource)
        except QuotaExceededError as exc:
            raise HTTPException(status_code=429, detail=str(exc))

    return dependency


CurrentUser = Annotated[dict, Depends(get_current_user)]


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

    @app.post("/api/auth/signup")
    def signup(body: AuthRequest):
        try:
            return _get_auth_service().signup(body.email, body.password)
        except UserAlreadyExistsError:
            raise HTTPException(
                status_code=400, detail="An account with that email already exists."
            )
        except InvalidEmailError:
            raise HTTPException(status_code=400, detail="Enter a valid email address.")
        except WeakPasswordError:
            raise HTTPException(
                status_code=400, detail="Password must be at least 8 characters."
            )

    @app.post("/api/auth/login")
    def login(body: AuthRequest):
        try:
            return _get_auth_service().login(body.email, body.password)
        except InvalidCredentialsError:
            raise HTTPException(status_code=401, detail="Incorrect email or password.")

    @app.post("/api/auth/logout")
    def logout(request: Request, user: CurrentUser):
        _, _, token = request.headers.get("Authorization", "").partition(" ")
        _get_auth_service().revoke_token(token)
        return {"status": "ok"}

    @app.get("/api/auth/me")
    def me(user: CurrentUser):
        return user

    @app.get("/api/auth/quota")
    def quota(user: CurrentUser):
        return _get_quota_service().status(user)

    @app.post("/api/ingest/{ticker}")
    def ingest(ticker: str, user: CurrentUser, quota: dict = Depends(require_quota(RESOURCE_ANALYSES))):
        ticker = ticker.upper()
        try:
            return _get_ingest_service().ingest(ticker)
        except TickerNotFoundError as exc:
            _get_quota_service().refund(user, RESOURCE_ANALYSES)
            raise HTTPException(status_code=404, detail=str(exc))
        except SECDownloadError:
            _get_quota_service().refund(user, RESOURCE_ANALYSES)
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
    def refresh_numbers(ticker: str, user: CurrentUser, quota: dict = Depends(require_quota(RESOURCE_ANALYSES))):
        ticker = ticker.upper()
        try:
            return _get_numbers_service().refresh(ticker)
        except TickerNotFoundError as exc:
            _get_quota_service().refund(user, RESOURCE_ANALYSES)
            raise HTTPException(status_code=404, detail=str(exc))
        except XBRLEdgarError:
            _get_quota_service().refund(user, RESOURCE_ANALYSES)
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


def _get_auth_service():
    return services.get_auth_service()


def _get_quota_service():
    return services.get_quota_service()


app = create_app()
