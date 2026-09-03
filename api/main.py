from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api import services
from financial_analyst.auth.quota import (
    RESOURCE_ANALYSES,
    RESOURCE_CHAT,
    QuotaExceededError,
)
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
from financial_analyst.steps import STEP_ONE
from financial_analyst.steps.chat import UnsupportedStepError
from financial_analyst.steps.generation import ArtifactValidationError, NoSourceError
from financial_analyst.steps.retrieval import EmbedModelMismatchError


class PriceOverride(BaseModel):
    price: float


class AuthRequest(BaseModel):
    email: str
    password: str


class GateRequest(BaseModel):
    decision: Literal["accept", "reject"]


class ChatRequest(BaseModel):
    step: int
    question: str
    search_all: bool = False


class PeersRequest(BaseModel):
    peers: list[str]


def _no_source_detail(ticker: str) -> str:
    return (
        f"No numbers or indexed source material for {ticker}; "
        "refresh numbers and ingest the ticker first."
    )


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

    @app.get("/api/steps/{ticker}/one-pager")
    def get_one_pager(ticker: str, user: CurrentUser):
        ticker = ticker.upper()
        result = _get_steps_service().one_pager(user["email"], ticker)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"No numbers for {ticker}; refresh numbers first.",
            )
        return result

    @app.post("/api/steps/{ticker}/gate")
    def set_step_gate(ticker: str, body: GateRequest, user: CurrentUser):
        ticker = ticker.upper()
        result = _get_steps_service().set_gate(user["email"], ticker, STEP_ONE, body.decision)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"No numbers for {ticker}; refresh numbers first.",
            )
        return result

    @app.get("/api/steps/{ticker}/business-swot")
    def get_business_swot(ticker: str, user: CurrentUser):
        ticker = ticker.upper()
        try:
            result = _get_steps_service().business_swot(user["email"], ticker)
        except ArtifactValidationError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Could not produce a grounded draft: {exc}",
            )
        except EmbedModelMismatchError as exc:
            raise HTTPException(
                status_code=503,
                detail=str(exc),
            )
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"No corpus for {ticker}; ingest first.",
            )
        return result

    @app.get("/api/steps/{ticker}/financials")
    def get_financials(ticker: str, user: CurrentUser):
        ticker = ticker.upper()
        try:
            result = _get_steps_service().financials(user["email"], ticker)
        except ArtifactValidationError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Could not produce a grounded draft: {exc}",
            )
        except EmbedModelMismatchError as exc:
            raise HTTPException(
                status_code=503,
                detail=str(exc),
            )
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=_no_source_detail(ticker),
            )
        return result

    @app.get("/api/steps/{ticker}/strategy")
    def get_strategy(ticker: str, user: CurrentUser):
        ticker = ticker.upper()
        try:
            result = _get_steps_service().strategy(user["email"], ticker)
        except ArtifactValidationError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Could not produce a grounded draft: {exc}",
            )
        except EmbedModelMismatchError as exc:
            raise HTTPException(
                status_code=503,
                detail=str(exc),
            )
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=_no_source_detail(ticker),
            )
        return result

    @app.post("/api/steps/{ticker}/chat")
    def chat(
        ticker: str,
        body: ChatRequest,
        user: CurrentUser,
        quota: dict = Depends(require_quota(RESOURCE_CHAT)),
    ):
        ticker = ticker.upper()
        if not body.question.strip():
            _get_quota_service().refund(user, RESOURCE_CHAT)
            raise HTTPException(status_code=400, detail="Question cannot be empty.")
        try:
            result = _get_steps_service().chat(
                user["email"],
                ticker,
                body.step,
                body.question.strip(),
                body.search_all,
            )
        except UnsupportedStepError as exc:
            _get_quota_service().refund(user, RESOURCE_CHAT)
            raise HTTPException(status_code=400, detail=str(exc))
        except NoSourceError:
            _get_quota_service().refund(user, RESOURCE_CHAT)
            raise HTTPException(status_code=404, detail=_no_source_detail(ticker))
        except ArtifactValidationError as exc:
            _get_quota_service().refund(user, RESOURCE_CHAT)
            raise HTTPException(
                status_code=502,
                detail=f"Could not produce a grounded answer: {exc}",
            )
        except EmbedModelMismatchError as exc:
            _get_quota_service().refund(user, RESOURCE_CHAT)
            raise HTTPException(status_code=503, detail=str(exc))
        if result is None:
            _get_quota_service().refund(user, RESOURCE_CHAT)
            raise HTTPException(
                status_code=404,
                detail=_no_source_detail(ticker),
            )
        return result

    @app.get("/api/steps/{ticker}/peers")
    def get_peers(ticker: str, user: CurrentUser):
        ticker = ticker.upper()
        result = _get_steps_service().peers(user["email"], ticker)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"No numbers for {ticker}; refresh numbers first.",
            )
        return result

    @app.put("/api/steps/{ticker}/peers")
    def set_peers(
        ticker: str,
        body: PeersRequest,
        user: CurrentUser,
        quota: dict = Depends(require_quota(RESOURCE_ANALYSES)),
    ):
        ticker = ticker.upper()
        try:
            result = _get_steps_service().set_peers(user["email"], ticker, body.peers)
        except TickerNotFoundError as exc:
            _get_quota_service().refund(user, RESOURCE_ANALYSES)
            raise HTTPException(status_code=404, detail=str(exc))
        except (SECDownloadError, XBRLEdgarError):
            _get_quota_service().refund(user, RESOURCE_ANALYSES)
            raise HTTPException(status_code=503, detail="SEC EDGAR unavailable, try again later")
        if result is None:
            _get_quota_service().refund(user, RESOURCE_ANALYSES)
            raise HTTPException(
                status_code=404,
                detail=f"No numbers for {ticker}; refresh numbers first.",
            )
        if not result.get("fetched"):
            _get_quota_service().refund(user, RESOURCE_ANALYSES)
        return result

    @app.delete("/api/steps/{ticker}/peers")
    def clear_peers(ticker: str, user: CurrentUser):
        ticker = ticker.upper()
        return _get_steps_service().clear_peers(user["email"], ticker)

    @app.get("/api/steps/{ticker}/done")
    def get_done_marks(ticker: str, user: CurrentUser):
        ticker = ticker.upper()
        result = _get_steps_service().done_status(user["email"], ticker)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"No numbers for {ticker}; refresh numbers first.",
            )
        return result

    @app.post("/api/steps/{ticker}/done/{step}")
    def mark_step_done(
        ticker: str,
        user: CurrentUser,
        step: int = Path(ge=1, le=4),
    ):
        ticker = ticker.upper()
        result = _get_steps_service().mark_done(user["email"], ticker, step)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"No numbers for {ticker}; refresh numbers first.",
            )
        return result

    @app.delete("/api/steps/{ticker}/done/{step}")
    def unmark_step_done(
        ticker: str,
        user: CurrentUser,
        step: int = Path(ge=1, le=4),
    ):
        ticker = ticker.upper()
        result = _get_steps_service().unmark_done(user["email"], ticker, step)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"No numbers for {ticker}; refresh numbers first.",
            )
        return result

    @app.get("/api/steps/{ticker}/valuation")
    def get_valuation(
        ticker: str,
        user: CurrentUser,
        discount_rate: float | None = None,
        growth: float | None = None,
    ):
        ticker = ticker.upper()
        result = _get_steps_service().valuation(
            user["email"], ticker, discount_rate=discount_rate, growth=growth
        )
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"No numbers for {ticker}; refresh numbers first.",
            )
        return result

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


def _get_steps_service():
    return services.get_steps_service()


app = create_app()
