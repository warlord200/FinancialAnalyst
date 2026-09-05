"""Tests that a new company's ingest runs the automated smoke eval.

``IngestService`` accepts an optional ``smoke_eval`` callable; the API
wiring supplies one that runs the per-company smoke gate once the corpus
is built. The job result then carries the smoke outcome (advisory — a
smoke failure never fails the ingest job itself). These tests use a stub
callable so no embedder or network is involved.
"""

from pathlib import Path

import pytest
from llama_index.core import Settings
from llama_index.core.embeddings.mock_embed_model import MockEmbedding
from llama_index.core.llms import MockLLM

from api.services import IngestService
from financial_analyst.indexing.company_index import CompanyIndex
from financial_analyst.ingestion.sec_downloader import TickerNotFoundError
from financial_analyst.jobs import InlineJobRunner, JobStore
from financial_analyst.reader.chunker import chunk_documents
from financial_analyst.reader.sec_html_reader import SECHtmlReader
from financial_analyst.storage.registry import CacheRegistry

FIXTURE_HTML = """<?xml version='1.0' encoding='ASCII'?>
<html><body>
<h2>Item 1.</h2><p>Tesla designs and manufactures electric vehicles.</p>
<h2>Item 1A.</h2><p>We face significant competition risk.</p>
<h2>Item 7.</h2><p>Revenue grew strongly. Liquidity remains healthy.</p>
<h2>Item 8.</h2><p>Total assets were 100 billion.</p>
</body></html>"""


class FakeDownloader:
    def __init__(self, filings_by_ticker):
        self.filings_by_ticker = {k.upper(): v for k, v in filings_by_ticker.items()}

    def validate_ticker(self, ticker):
        return ticker.upper() in self.filings_by_ticker

    def download_filings(self, ticker, num_10k=3, num_10q=4):
        if ticker.upper() not in self.filings_by_ticker:
            raise TickerNotFoundError(ticker)
        return self.filings_by_ticker[ticker.upper()]


def make_filings(tmp_path, ticker, year_form_pairs):
    filings = []
    for i, (year, form) in enumerate(year_form_pairs):
        d = tmp_path / "data" / str(year)
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{ticker}_{form}_{year}_{i}.htm"
        p.write_text(FIXTURE_HTML, encoding="utf-8")
        filings.append(
            {
                "form": form,
                "fiscal_year": year,
                "filing_date": f"{year}-01-01",
                "path": str(p),
            }
        )
    return filings


@pytest.fixture
def mock_models():
    old_embed, old_llm = Settings._embed_model, Settings._llm
    Settings.embed_model = MockEmbedding(embed_dim=8)
    Settings.llm = MockLLM()
    try:
        yield
    finally:
        Settings._embed_model = old_embed
        Settings._llm = old_llm


def make_service(tmp_path, smoke_eval=None, filings_by_ticker=None):
    filings_by_ticker = filings_by_ticker or {
        "TSLA": make_filings(tmp_path, "TSLA", [(2025, "10-K")])
    }
    return IngestService(
        downloader=FakeDownloader(filings_by_ticker),
        registry=CacheRegistry(str(tmp_path / "storage" / "ingest_registry.json")),
        index=CompanyIndex(
            chroma_path=str(tmp_path / "chroma"), storage_base=str(tmp_path / "storage")
        ),
        job_store=JobStore(str(tmp_path / "storage" / "jobs.db")),
        runner=InlineJobRunner(),
        reader=SECHtmlReader(),
        chunker=chunk_documents,
        smoke_eval=smoke_eval,
    )


def test_ingest_runs_smoke_and_records_it_in_the_job_result(tmp_path, mock_models):
    smoke = {"ticker": "TSLA", "passed": True, "steps": {}}
    calls = []

    def smoke_eval(ticker):
        calls.append(ticker)
        return smoke

    service = make_service(tmp_path, smoke_eval=smoke_eval)
    submitted = service.ingest("TSLA")
    job = service.job_store.get(submitted["job_id"])
    assert job["status"] == "completed"
    assert calls == ["TSLA"]
    assert job["result"]["num_chunks"] > 0
    assert job["result"]["smoke"] == smoke


def test_ingest_without_smoke_hook_has_no_smoke_key(tmp_path, mock_models):
    service = make_service(tmp_path, smoke_eval=None)
    submitted = service.ingest("TSLA")
    job = service.job_store.get(submitted["job_id"])
    assert job["status"] == "completed"
    assert "smoke" not in job["result"]


def test_smoke_failure_does_not_fail_the_ingest_job(tmp_path, mock_models):
    def smoke_eval(ticker):
        raise RuntimeError("embedding backend down")

    service = make_service(tmp_path, smoke_eval=smoke_eval)
    submitted = service.ingest("TSLA")
    job = service.job_store.get(submitted["job_id"])
    assert job["status"] == "completed"
    assert "embedding backend down" in job["result"]["smoke_error"]
