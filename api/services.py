from datetime import datetime, timezone

import torch
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.deepseek import DeepSeek

from financial_analyst import config
from financial_analyst.analysis.analyzer import Analyzer
from financial_analyst.indexing.company_index import CompanyIndex
from financial_analyst.ingestion.sec_downloader import SECDownloader, TickerNotFoundError
from financial_analyst.jobs import JobRunner, JobStore, ThreadJobRunner
from financial_analyst.reader.chunker import chunk_documents
from financial_analyst.reader.sec_html_reader import SECHtmlReader
from financial_analyst.storage.registry import CacheRegistry

_analyzer: Analyzer | None = None
_ingest_service: "IngestService | None" = None
_embed_model = None
_llm = None

NUM_10K = 3
NUM_10Q = 4


def _ensure_models():
    global _embed_model, _llm
    if _embed_model is None:
        device = str(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
        _embed_model = HuggingFaceEmbedding(
            model_name="Octen/Octen-Embedding-4B-INT8",
            device=device,
        )
        Settings.embed_model = _embed_model
    if _llm is None:
        _llm = DeepSeek(model="deepseek-v4-flash", api_key=config.get_deepseek_api_key())
        Settings.llm = _llm
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
