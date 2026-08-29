from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from llama_index.core import Settings
from llama_index.core.embeddings.mock_embed_model import MockEmbedding
from llama_index.core.llms import MockLLM

import api.main as main
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
        self.download_calls = 0
        self.validate_calls = 0

    def validate_ticker(self, ticker):
        self.validate_calls += 1
        return ticker.upper() in self.filings_by_ticker

    def download_filings(self, ticker, num_10k=3, num_10q=4):
        self.download_calls += 1
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


def make_client(tmp_path, monkeypatch, filings_by_ticker):
    service = IngestService(
        downloader=FakeDownloader(filings_by_ticker),
        registry=CacheRegistry(str(tmp_path / "storage" / "ingest_registry.json")),
        index=CompanyIndex(
            chroma_path=str(tmp_path / "chroma"), storage_base=str(tmp_path / "storage")
        ),
        job_store=JobStore(str(tmp_path / "storage" / "jobs.json")),
        runner=InlineJobRunner(),
        reader=SECHtmlReader(),
        chunker=chunk_documents,
    )
    monkeypatch.setattr(main, "_get_ingest_service", lambda: service)
    client = TestClient(main.create_app())
    return client, service


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


@pytest.fixture
def tsla_filings(tmp_path):
    return make_filings(
        tmp_path, "TSLA", [(2025, "10-K"), (2024, "10-K"), (2025, "10-Q")]
    )


def test_ingest_unknown_ticker_returns_404(tmp_path, monkeypatch, tsla_filings, mock_models):
    client, _ = make_client(tmp_path, monkeypatch, {"TSLA": tsla_filings})
    resp = client.post("/api/ingest/NOPE")
    assert resp.status_code == 404


def test_ingest_runs_job_to_completion(tmp_path, monkeypatch, tsla_filings, mock_models):
    client, _ = make_client(tmp_path, monkeypatch, {"TSLA": tsla_filings})

    resp = client.post("/api/ingest/TSLA")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "submitted"
    assert body["ticker"] == "TSLA"
    job_id = body["job_id"]

    job = client.get(f"/api/ingest/jobs/{job_id}").json()
    assert job["status"] == "completed"
    assert job["progress"] == 100
    assert job["result"]["num_chunks"] > 0
    assert "ITEM 7" in job["result"]["chunks_by_item"]


def test_ingest_cached_ticker_returns_instantly(tmp_path, monkeypatch, tsla_filings, mock_models):
    client, service = make_client(tmp_path, monkeypatch, {"TSLA": tsla_filings})

    client.post("/api/ingest/TSLA")
    assert service.downloader.download_calls == 1

    validate_before = service.downloader.validate_calls
    resp = client.post("/api/ingest/TSLA")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cached"
    assert service.downloader.download_calls == 1
    assert service.downloader.validate_calls == validate_before


def test_get_job_404_for_unknown_job(tmp_path, monkeypatch, tsla_filings, mock_models):
    client, _ = make_client(tmp_path, monkeypatch, {"TSLA": tsla_filings})
    resp = client.get("/api/ingest/jobs/nope")
    assert resp.status_code == 404


def test_get_stats_reports_chunk_metadata(tmp_path, monkeypatch, tsla_filings, mock_models):
    client, _ = make_client(tmp_path, monkeypatch, {"TSLA": tsla_filings})
    client.post("/api/ingest/TSLA")

    resp = client.get("/api/ingest/TSLA/stats")
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["ticker"] == "TSLA"
    assert stats["num_chunks"] > 0
    assert stats["fiscal_years"] == [2025, 2024]
    assert set(stats["chunks_by_item"].keys()) == {"ITEM 1", "ITEM 1A", "ITEM 7", "ITEM 8"}
    assert stats["chunks_by_year"]["2025"] >= 2


def test_stats_404_when_not_ingested(tmp_path, monkeypatch, tsla_filings, mock_models):
    client, _ = make_client(tmp_path, monkeypatch, {"TSLA": tsla_filings})
    resp = client.get("/api/ingest/TSLA/stats")
    assert resp.status_code == 404


def test_list_ingested(tmp_path, monkeypatch, tsla_filings, mock_models):
    client, _ = make_client(tmp_path, monkeypatch, {"TSLA": tsla_filings})
    assert client.get("/api/ingest").json() == []
    client.post("/api/ingest/TSLA")

    entries = client.get("/api/ingest").json()
    assert [e["ticker"] for e in entries] == ["TSLA"]
    assert entries[0]["fiscal_years"] == [2025, 2024]
