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

SUBMISSIONS_MIXED = {
    "cik": "1318605",
    "filings": {
        "recent": {
            "form": [
                "10-K", "10-Q", "10-K", "10-Q", "10-Q", "10-Q", "10-K",
            ],
            "filingDate": [
                "2026-01-29",
                "2026-04-30",
                "2025-01-29",
                "2025-10-30",
                "2025-07-30",
                "2025-04-30",
                "2024-01-29",
            ],
            "reportDate": [
                "2025-12-31",
                "2026-03-31",
                "2024-12-31",
                "2025-09-30",
                "2025-06-30",
                "2025-03-31",
                "2023-12-31",
            ],
            "accessionNumber": [
                "0001628280-26-003952",
                "0001628280-26-001122",
                "0001628280-25-000001",
                "0001628280-25-009921",
                "0001628280-25-006644",
                "0001628280-25-003311",
                "0001628280-24-000001",
            ],
            "primaryDocument": [
                "tsla-20251231.htm",
                "tsla-20260331.htm",
                "tsla-20241231.htm",
                "tsla-20250930.htm",
                "tsla-20250630.htm",
                "tsla-20250331.htm",
                "tsla-20231231.htm",
            ],
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


def test_download_filings_fetches_10ks_and_four_10qs(tmp_path):
    def responder(url, headers=None, timeout=None):
        if "company_tickers.json" in url:
            return FakeResponse(COMPANY_TICKERS)
        if "submissions/CIK" in url:
            return FakeResponse(SUBMISSIONS_MIXED)
        if "Archives/edgar/data" in url:
            return FakeResponse(PRIMARY_HTML)
        raise AssertionError(f"Unexpected URL: {url}")

    with patch(
        "financial_analyst.ingestion.sec_downloader.requests.get", side_effect=responder
    ):
        dl = SECDownloader(data_dir=str(tmp_path))
        filings = dl.download_filings("TSLA")

    forms = [f["form"] for f in filings]
    assert forms.count("10-K") == 3
    assert forms.count("10-Q") == 4
    names = sorted(Path(f["path"]).name for f in filings)
    assert len(set(names)) == len(names)
    assert all(f["fiscal_year"] for f in filings)


def test_download_filings_unknown_ticker_raises(tmp_path):
    with patch(
        "financial_analyst.ingestion.sec_downloader.requests.get", return_value=FakeResponse({})
    ):
        dl = SECDownloader(data_dir=str(tmp_path))
        with pytest.raises(TickerNotFoundError):
            dl.download_filings("ZZZZ")


def test_validate_ticker_true_and_false(tmp_path):
    def responder(url, headers=None, timeout=None):
        if "company_tickers.json" in url:
            return FakeResponse(COMPANY_TICKERS)
        raise AssertionError(f"Unexpected URL: {url}")

    with patch(
        "financial_analyst.ingestion.sec_downloader.requests.get", side_effect=responder
    ):
        dl = SECDownloader(data_dir=str(tmp_path))
        assert dl.validate_ticker("TSLA") is True
        assert dl.validate_ticker("ZZZZ") is False
