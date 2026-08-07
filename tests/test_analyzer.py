from pathlib import Path
from unittest.mock import MagicMock

from financial_analyst.analysis.analyzer import Analyzer


class FakeDownloader:
    def __init__(self, filings):
        self._filings = filings
        self.calls = 0

    def download_10k(self, ticker, num_filings=2):
        self.calls += 1
        return self._filings


class FakeCustomDocs:
    def __init__(self):
        self.vec_idx = MagicMock()
        self.summ_idx = MagicMock()

    def get_indexes(self):
        return self.vec_idx, self.summ_idx


def make_analyzer(tmp_path, filings):
    downloader = FakeDownloader(filings)
    from financial_analyst.storage.registry import CacheRegistry

    registry = CacheRegistry(str(tmp_path / "registry.json"))
    return Analyzer(downloader, registry, llm=MagicMock(), chroma_path=str(tmp_path / "chroma"), storage_base=str(tmp_path / "storage"))


def make_filings(tmp_path):
    d = tmp_path / "2025"
    d.mkdir(parents=True)
    path = d / "TSLA.htm"
    path.write_text("<html><body><p>x</p></body></html>", encoding="utf-8")
    return [{"fiscal_year": 2025, "filing_date": "2026-01-29", "path": str(path)}]


def test_analyze_new_ticker_downloads_and_builds(tmp_path):
    filings = make_filings(tmp_path)
    a = make_analyzer(tmp_path, filings)
    a._build_custom_docs = MagicMock(return_value={2025: FakeCustomDocs()})
    a._generate_report = MagicMock(
        return_value={"ticker": "TSLA", "fiscal_years": [2025], "generated_at": "t",
                      "verdict": {"label": "neutral", "score": 50, "rationale": "x"},
                      "markdown": "# Executive Summary\n\nbody"}
    )

    result = a.analyze("TSLA")
    assert result["status"] == "completed"
    assert a.downloader.calls == 1
    assert a.registry.get("TSLA") is not None
    assert Path(result["report_path"]).is_file()


def test_analyze_cached_ticker_skips_download(tmp_path):
    filings = make_filings(tmp_path)
    a = make_analyzer(tmp_path, filings)
    a._build_custom_docs = MagicMock(return_value={2025: FakeCustomDocs()})
    a._generate_report = MagicMock(
        return_value={"ticker": "TSLA", "fiscal_years": [2025], "generated_at": "t",
                      "verdict": {"label": "neutral", "score": 50, "rationale": "x"},
                      "markdown": "# Executive Summary\n\nbody"}
    )
    a.analyze("TSLA")
    a.downloader.calls = 0

    result = a.analyze("TSLA")
    assert result["status"] == "cached"
    assert a.downloader.calls == 0


def test_get_report_returns_none_when_missing(tmp_path):
    a = make_analyzer(tmp_path, [])
    assert a.get_report("MSFT") is None


def test_reanalyze_forces_fresh_analysis(tmp_path):
    filings = make_filings(tmp_path)
    a = make_analyzer(tmp_path, filings)
    a._build_custom_docs = MagicMock(return_value={2025: FakeCustomDocs()})
    a._generate_report = MagicMock(
        return_value={"ticker": "TSLA", "fiscal_years": [2025], "generated_at": "t",
                      "verdict": {"label": "neutral", "score": 50, "rationale": "x"},
                      "markdown": "# Executive Summary\n\nbody"}
    )
    a.analyze("TSLA")
    a.downloader.calls = 0

    result = a.reanalyze("TSLA")
    assert result["status"] == "completed"
    assert a.downloader.calls == 1
