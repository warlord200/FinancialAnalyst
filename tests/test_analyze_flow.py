from pathlib import Path
from unittest.mock import MagicMock

from llama_index.core import Settings
from llama_index.core.embeddings.mock_embed_model import MockEmbedding
from llama_index.core.llms import MockLLM

from financial_analyst.analysis.analyzer import Analyzer
from financial_analyst.reader.sec_html_reader import SECHtmlReader
from financial_analyst.storage.registry import CacheRegistry


FIXTURE_HTML = """<html><body>
<h2>Item 1.</h2><p>Company makes electric vehicles.</p>
<h2>Item 1A.</h2><p>Competition risk is significant.</p>
<h2>Item 7.</h2><p>Revenue grew strongly this year.</p>
<h2>Item 8.</h2><p>Total assets 100 billion. Operating cash flow 15 billion.</p>
</body></html>"""


class FakeLLM:
    def complete(self, prompt: str):
        r = MagicMock()
        r.text = '{"label": "bullish", "score": 75, "rationale": "Strong growth."}'
        return r


def test_end_to_end_analyze_then_cached(tmp_path):
    data = tmp_path / "data"
    (data / "2025").mkdir(parents=True)
    (data / "2024").mkdir()
    (data / "2025" / "TSLA.htm").write_text(FIXTURE_HTML, encoding="utf-8")
    (data / "2024" / "TSLA.htm").write_text(FIXTURE_HTML, encoding="utf-8")

    filings = [
        {"fiscal_year": 2025, "filing_date": "2026-01-29", "path": str(data / "2025" / "TSLA.htm")},
        {"fiscal_year": 2024, "filing_date": "2025-01-29", "path": str(data / "2024" / "TSLA.htm")},
    ]

    class FakeDownloader:
        calls = 0

        def download_10k(self, ticker, num_filings=2):
            FakeDownloader.calls += 1
            return filings

    old_embed, old_llm = Settings._embed_model, Settings._llm
    Settings.embed_model = MockEmbedding(embed_dim=8)
    Settings.llm = MockLLM()
    try:
        registry = CacheRegistry(str(tmp_path / "storage" / "registry.json"))
        extractor = {".htm": SECHtmlReader()}
        analyzer = Analyzer(
            FakeDownloader(),
            registry,
            FakeLLM(),
            chroma_path=str(tmp_path / "chroma"),
            storage_base=str(tmp_path / "storage"),
            file_extractor=extractor,
        )

        first = analyzer.analyze("TSLA")
        assert first["status"] == "completed"
        assert FakeDownloader.calls == 1
        report_path = Path(first["report_path"])
        assert report_path.is_file()
        assert "TSLA" in report_path.read_text(encoding="utf-8")

        # Cache hit: downloader not called again
        FakeDownloader.calls = 0
        second = analyzer.analyze("TSLA")
        assert second["status"] == "cached"
        assert FakeDownloader.calls == 0

        fetched = analyzer.get_report("TSLA")
        assert fetched is not None
        assert fetched["verdict"]["label"] == "bullish"
        assert fetched["markdown"].startswith("# Executive Summary")
    finally:
        Settings._embed_model = old_embed
        Settings._llm = old_llm
