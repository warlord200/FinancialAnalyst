# tests/test_sec_downloader.py
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from financial_analyst.ingestion.sec_downloader import (
    SECDownloadError,
    SECDownloader,
    TickerNotFoundError,
)


class FakeResponse:
    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if isinstance(self.data, str):
            return json.loads(self.data)
        return self.data

    @property
    def text(self):
        return self.data if isinstance(self.data, str) else json.dumps(self.data)


COMPANY_TICKERS = {
    "0": {"cik_str": 1318605, "ticker": "TSLA", "title": "Tesla, Inc."},
}

SUBMISSIONS = {
    "cik": "1318605",
    "filings": {
        "recent": {
            "form": ["10-K", "10-K"],
            "filingDate": ["2026-01-29", "2025-01-29"],
            "reportDate": ["2025-12-31", "2024-12-31"],
            "accessionNumber": ["0001628280-26-003952", "0001628280-25-000001"],
            "primaryDocument": ["tsla-20251231.htm", "tsla-20241231.htm"],
        }
    },
}

PRIMARY_HTML = "<html><body><h1>Item 1.</h1><p>Business</p></body></html>"


def make_responder():
    def responder(url, headers=None, timeout=None):
        if "company_tickers.json" in url:
            return FakeResponse(COMPANY_TICKERS)
        if "submissions/CIK" in url:
            return FakeResponse(SUBMISSIONS)
        if "Archives/edgar/data" in url:
            return FakeResponse(PRIMARY_HTML)
        raise AssertionError(f"Unexpected URL: {url}")

    return responder


def test_download_10k_downloads_two_filings(tmp_path):
    with patch(
        "financial_analyst.ingestion.sec_downloader.requests.get", side_effect=make_responder()
    ):
        dl = SECDownloader(data_dir=str(tmp_path))
        filings = dl.download_10k("TSLA")

    assert len(filings) == 2
    assert filings[0]["fiscal_year"] == 2025
    assert filings[0]["filing_date"] == "2026-01-29"
    assert filings[1]["fiscal_year"] == 2024

    p = Path(filings[0]["path"])
    assert p.name == "TSLA.htm"
    assert p.read_text(encoding="utf-8") == PRIMARY_HTML
    assert Path(filings[1]["path"]).name == "TSLA.htm"


def test_download_10k_unknown_ticker_raises(tmp_path):
    with patch(
        "financial_analyst.ingestion.sec_downloader.requests.get", return_value=FakeResponse({})
    ):
        dl = SECDownloader(data_dir=str(tmp_path))
        with pytest.raises(TickerNotFoundError):
            dl.download_10k("ZZZZ")


def test_download_10k_retries_on_rate_limit(tmp_path):
    class Flaky:
        def __init__(self):
            self.calls = 0

        def __call__(self, url, headers=None, timeout=None):
            self.calls += 1
            if "Archives/edgar/data" in url and self.calls == 3:
                return FakeResponse({}, status_code=429)
            if "company_tickers.json" in url:
                return FakeResponse(COMPANY_TICKERS)
            if "submissions/CIK" in url:
                return FakeResponse(SUBMISSIONS)
            return FakeResponse(PRIMARY_HTML)

    with patch(
        "financial_analyst.ingestion.sec_downloader.requests.get", side_effect=Flaky()
    ) as mock_get:
        dl = SECDownloader(data_dir=str(tmp_path), max_retries=3)
        filings = dl.download_10k("TSLA")

    assert len(filings) == 2
    archives_hits = sum(
        1
        for call in mock_get.call_args_list
        if "Archives/edgar/data" in call.args[0]
    )
    assert archives_hits == 3  # 2 filings + 1 rate-limit retry


def test_download_10k_raises_after_max_retries(tmp_path):
    def fail(url, headers=None, timeout=None):
        if "Archives/edgar/data" in url:
            return FakeResponse({}, status_code=429)
        if "company_tickers.json" in url:
            return FakeResponse(COMPANY_TICKERS)
        return FakeResponse(SUBMISSIONS)

    with patch(
        "financial_analyst.ingestion.sec_downloader.requests.get", side_effect=fail
    ):
        dl = SECDownloader(data_dir=str(tmp_path), max_retries=2)
        with pytest.raises(SECDownloadError):
            dl.download_10k("TSLA")
