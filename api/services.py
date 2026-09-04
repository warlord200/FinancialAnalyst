from datetime import datetime, timezone
import os

from llama_index.core import Settings
from llama_index.llms.deepseek import DeepSeek

from financial_analyst import config
from financial_analyst.analysis.analyzer import Analyzer
from financial_analyst.auth.quota import QuotaService, QuotaStore
from financial_analyst.auth.sessions import RevokedTokenStore
from financial_analyst.auth.tokens import load_or_create_secret
from financial_analyst.auth.users import AuthService, UserStore
from financial_analyst.indexing.company_index import CompanyIndex
from financial_analyst.ingestion.sec_downloader import SECDownloader, TickerNotFoundError
from financial_analyst.jobs import JobRunner, JobStore, ThreadJobRunner
from financial_analyst.numbers.prices import PriceStore, YahooFinancePriceClient
from financial_analyst.numbers.service import NumbersService, NumbersStore
from financial_analyst.numbers.xbrl import fetch_company_facts
from financial_analyst.reader.chunker import chunk_documents
from financial_analyst.reader.sec_html_reader import SECHtmlReader
from financial_analyst.steps.chat import ChatService
from financial_analyst.steps.drafts import DraftStore
from financial_analyst.steps.generation import ArtifactGenerator
from financial_analyst.steps.retrieval import (
    CloudflareEmbedding,
    EMBED_QUERY_INSTRUCTION,
    ScopedRetriever,
    reranker_from_env,
)
from financial_analyst.steps.service import StepsService
from financial_analyst.steps.state import PeerStateStore, StepStateStore
from financial_analyst.storage.registry import CacheRegistry

_analyzer: Analyzer | None = None
_ingest_service: "IngestService | None" = None
_numbers_service: "NumbersService | None" = None
_auth_service: "AuthService | None" = None
_quota_service: "QuotaService | None" = None
_steps_service: "StepsService | None" = None
_embed_model = None
_llm = None
_draft_llm = None

NUM_10K = 3
NUM_10Q = 4


def _build_llm(*, thinking: bool = True):
    kwargs = (
        {"timeout": 180.0}
        if thinking
        else {
            "additional_kwargs": {"extra_body": {"thinking": {"type": "disabled"}}}
        }
    )
    return DeepSeek(
        model="deepseek-v4-flash",
        api_key=config.get_deepseek_api_key(),
        **kwargs,
    )


def _ensure_models():
    global _embed_model, _llm, _draft_llm
    if _embed_model is None:
        account_id, api_token = config.get_cloudflare_credentials()
        if not account_id or not api_token:
            raise RuntimeError(
                "Cloudflare Workers AI is not configured: set CLOUDFLARE_ACCOUNT_ID "
                "and CLOUDFLARE_API_TOKEN in .env to embed corpora"
            )
        batch_size = int(os.getenv("EMBED_BATCH_SIZE", "32"))
        _embed_model = CloudflareEmbedding(
            account_id=account_id,
            api_key=api_token,
            query_instruction=EMBED_QUERY_INSTRUCTION,
            embed_batch_size=batch_size,
        )
        Settings.embed_model = _embed_model
    if _llm is None:
        _llm = _build_llm()
        Settings.llm = _llm
    if _draft_llm is None:
        _draft_llm = _build_llm(thinking=False)
    return _embed_model, _llm


def get_analyzer() -> Analyzer:
    global _analyzer
    if _analyzer is not None:
        return _analyzer
    embed_model, llm = _ensure_models()

    downloader = SECDownloader(data_dir="./data")
    registry = CacheRegistry("./storage/registry.json")
    file_extractor = {".htm": SECHtmlReader()}

    _analyzer = Analyzer(
        downloader,
        registry,
        llm,
        chroma_path="./chroma_db",
        storage_base="./storage",
        file_extractor=file_extractor,
    )
    return _analyzer


class IngestService:
    def __init__(
        self,
        downloader: SECDownloader,
        registry: CacheRegistry,
        index: CompanyIndex,
        job_store: JobStore,
        runner: JobRunner,
        reader: SECHtmlReader | None = None,
        chunker=None,
        num_10k: int = NUM_10K,
        num_10q: int = NUM_10Q,
    ) -> None:
        self.downloader = downloader
        self.registry = registry
        self.index = index
        self.job_store = job_store
        self.runner = runner
        self.reader = reader or SECHtmlReader()
        self.chunker = chunker or chunk_documents
        self.num_10k = num_10k
        self.num_10q = num_10q

    def ingest(self, ticker: str) -> dict:
        ticker = ticker.upper()
        cached = self.registry.get(ticker)
        if cached:
            return {
                "status": "cached",
                "ticker": ticker,
                "ingested_at": cached["ingested_at"],
            }
        if not self.downloader.validate_ticker(ticker):
            raise TickerNotFoundError(f"Ticker not found on SEC EDGAR: {ticker}")
        job = self.job_store.create(ticker)
        self.runner.run(self.job_store, job["id"], lambda: self._ingest_sync(ticker, job["id"]))
        return {
            "status": "submitted",
            "ticker": ticker,
            "job_id": job["id"],
        }

    def _ingest_sync(self, ticker: str, job_id: str) -> dict:
        self.job_store.update(job_id, status="running", progress=20)
        filings = self.downloader.download_filings(
            ticker, num_10k=self.num_10k, num_10q=self.num_10q
        )
        self.job_store.update(job_id, progress=50)
        nodes = []
        for filing in filings:
            docs = self.reader.load_data(
                filing["path"],
                extra_info={
                    "ticker": ticker,
                    "fiscal_year": filing["fiscal_year"],
                    "filing": filing["form"],
                },
            )
            nodes.extend(self.chunker(docs))
        self.job_store.update(job_id, progress=70)
        num_chunks = self.index.build(ticker, nodes)
        stats = self.index.stats(ticker)
        self.registry.add(
            ticker,
            {
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "num_chunks": num_chunks,
                "fiscal_years": stats["fiscal_years"],
            },
        )
        self.job_store.update(job_id, progress=90)
        return stats

    def get_job(self, job_id: str) -> dict | None:
        return self.job_store.get(job_id)

    def list_ingested(self) -> list[dict]:
        return self.registry.list_all()

    def get_stats(self, ticker: str) -> dict | None:
        ticker = ticker.upper()
        entry = self.registry.get(ticker)
        if entry is None:
            return None
        stats = self.index.stats(ticker)
        return {
            "ticker": ticker,
            "ingested_at": entry["ingested_at"],
            "num_chunks": stats["num_chunks"],
            "chunks_by_item": stats["chunks_by_item"],
            "chunks_by_year": stats["chunks_by_year"],
            "fiscal_years": stats["fiscal_years"],
        }


def get_ingest_service() -> IngestService:
    global _ingest_service
    if _ingest_service is not None:
        return _ingest_service
    _ensure_models()
    _ingest_service = IngestService(
        downloader=SECDownloader(data_dir="./data"),
        registry=CacheRegistry("./storage/ingest_registry.json"),
        index=CompanyIndex(chroma_path="./chroma_db", storage_base="./storage"),
        job_store=JobStore("./storage/jobs.json"),
        runner=ThreadJobRunner(),
        reader=SECHtmlReader(),
        chunker=chunk_documents,
        num_10k=NUM_10K,
        num_10q=NUM_10Q,
    )
    return _ingest_service


def get_numbers_service() -> NumbersService:
    global _numbers_service
    if _numbers_service is not None:
        return _numbers_service
    downloader = SECDownloader(data_dir="./data")
    _numbers_service = NumbersService(
        downloader=downloader,
        facts_fetcher=fetch_company_facts,
        price_client=YahooFinancePriceClient(),
        store=NumbersStore("./storage/numbers.json"),
        price_store=PriceStore("./storage/prices.json"),
    )
    return _numbers_service


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is not None:
        return _auth_service
    _auth_service = AuthService(
        user_store=UserStore("./storage/auth.db"),
        secret=load_or_create_secret("./storage/auth_secret.key"),
        revoked_store=RevokedTokenStore("./storage/auth.db"),
    )
    return _auth_service


def get_quota_service() -> QuotaService:
    global _quota_service
    if _quota_service is not None:
        return _quota_service
    _quota_service = QuotaService(
        store=QuotaStore("./storage/quota.db"),
    )
    return _quota_service


def get_steps_service() -> StepsService:
    global _steps_service
    if _steps_service is not None:
        return _steps_service
    _ensure_models()
    retriever = ScopedRetriever(
        CompanyIndex(chroma_path="./chroma_db", storage_base="./storage"),
        reranker=reranker_from_env(),
    )
    generator = ArtifactGenerator(retriever, _draft_llm, repair_llm=_llm)
    chat_service = ChatService(retriever, Settings.llm)
    _steps_service = StepsService(
        numbers_service=get_numbers_service(),
        state_store=StepStateStore("./storage/steps.db"),
        generator=generator,
        draft_store=DraftStore("./storage/drafts.json"),
        chat_service=chat_service,
        peers_store=PeerStateStore("./storage/steps.db"),
    )
    return _steps_service
