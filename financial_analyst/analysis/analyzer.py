# financial_analyst/analysis/analyzer.py
import threading
from datetime import datetime, timezone
from pathlib import Path

from financial_analyst.analysis.report_generator import ReportGenerator
from financial_analyst.ingestion.sec_downloader import SECDownloader
from financial_analyst.indexing.CustomDocs import CustomDocs
from financial_analyst.storage.registry import CacheRegistry


class Analyzer:
    def __init__(
        self,
        downloader: SECDownloader,
        registry: CacheRegistry,
        llm,
        chroma_path: str = "./chroma_db",
        storage_base: str = "./storage",
        file_extractor: dict | None = None,
    ) -> None:
        self.downloader = downloader
        self.registry = registry
        self.llm = llm
        self.chroma_path = chroma_path
        self.storage_base = Path(storage_base)
        self.file_extractor = file_extractor
        self._locks: dict[str, threading.Lock] = {}

    _registry_lock = threading.Lock()

    def _lock_for(self, ticker: str) -> threading.Lock:
        ticker = ticker.upper()
        with self._registry_lock:
            if ticker not in self._locks:
                self._locks[ticker] = threading.Lock()
            return self._locks[ticker]

    def _build_custom_docs(self, ticker: str, filing: dict) -> CustomDocs:
        name = f"{ticker.upper()}_{filing['fiscal_year']}"
        return CustomDocs(
            name,
            filing["path"],
            f"{ticker} 10-K fiscal {filing['fiscal_year']}",
            self.file_extractor,
            chroma_path=self.chroma_path,
            storage_base=str(self.storage_base),
            requires_page_labels=False,
        )

    def _generate_report(self, ticker: str, docs_by_year: dict[int, CustomDocs]) -> dict:
        rg = ReportGenerator(docs_by_year, self.llm, ticker.upper())
        report = rg.generate()
        return {
            "ticker": report.ticker,
            "fiscal_years": report.fiscal_years,
            "generated_at": report.generated_at,
            "verdict": report.verdict,
            "markdown": report.markdown,
        }

    def _save_report(self, ticker: str, report: dict) -> str:
        out_dir = self.storage_base / ticker.upper()
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "report.md"
        path.write_text(report["markdown"], encoding="utf-8")
        return str(path)

    def analyze(self, ticker: str) -> dict:
        ticker = ticker.upper()
        lock = self._lock_for(ticker)
        with lock:
            cached = self.registry.get(ticker)
            if cached and Path(cached["report_path"]).is_file():
                return {"status": "cached", "report_path": cached["report_path"]}

            filings = self.downloader.download_10k(ticker)
            docs_by_year = {
                f["fiscal_year"]: self._build_custom_docs(ticker, f) for f in filings
            }
            report = self._generate_report(ticker, docs_by_year)
            report_path = self._save_report(ticker, report)
            self.registry.add(
                ticker,
                {
                    "fiscal_years": report["fiscal_years"],
                    "report_path": report_path,
                    "report_generated_at": datetime.now(timezone.utc).isoformat(),
                    "verdict": report["verdict"],
                },
            )
            return {"status": "completed", "report_path": report_path}

    def reanalyze(self, ticker: str) -> dict:
        ticker = ticker.upper()
        self.registry.clear(ticker)
        return self.analyze(ticker)

    def get_report(self, ticker: str) -> dict | None:
        ticker = ticker.upper()
        entry = self.registry.get(ticker)
        if entry is None:
            return None
        path = Path(entry["report_path"])
        if not path.is_file():
            return None
        return {
            "ticker": ticker,
            "fiscal_years": entry["fiscal_years"],
            "generated_at": entry["report_generated_at"],
            "verdict": entry["verdict"],
            "markdown": path.read_text(encoding="utf-8"),
        }

    def list_tickers(self) -> list[dict]:
        return self.registry.list_all()
