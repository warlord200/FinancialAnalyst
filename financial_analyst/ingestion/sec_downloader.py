# financial_analyst/ingestion/sec_downloader.py
import re
import time
from pathlib import Path

import requests

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVES_BASE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}"


class TickerNotFoundError(Exception):
    pass


class SECDownloadError(Exception):
    pass


class SECDownloader:
    def __init__(
        self,
        data_dir: str = "./data",
        user_agent: str = "FinancialAnalyst research@example.com",
        max_retries: int = 3,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.user_agent = user_agent
        self.max_retries = max_retries

    def _get(self, url: str) -> requests.Response:
        headers = {"User-Agent": self.user_agent}
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = requests.get(url, headers=headers, timeout=30)
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_exc = SECDownloadError(
                        f"SEC returned HTTP {resp.status_code} for {url}"
                    )
                    time.sleep(2**attempt)
                    continue
                resp.raise_for_status()
                return resp
            except (requests.RequestException, RuntimeError) as exc:
                last_exc = exc
                time.sleep(2**attempt)
        raise SECDownloadError(f"Failed to fetch {url} after {self.max_retries} attempts: {last_exc}")

    def _get_cik(self, ticker: str) -> int:
        data = self._get(COMPANY_TICKERS_URL).json()
        for entry in data.values():
            if entry["ticker"] == ticker.upper():
                return int(entry["cik_str"])
        raise TickerNotFoundError(f"Ticker not found on SEC EDGAR: {ticker}")

    def _get_recent_10k_filings(self, cik: int, num: int) -> list[dict]:
        data = self._get(SUBMISSIONS_URL.format(cik=cik)).json()
        recent = data["filings"]["recent"]
        filings = []
        for i in range(len(recent["form"])):
            if recent["form"][i] != "10-K":
                continue
            fiscal_year = int(recent["reportDate"][i][:4])
            accession = recent["accessionNumber"][i]
            filings.append(
                {
                    "fiscal_year": fiscal_year,
                    "filing_date": recent["filingDate"][i],
                    "accession_number": accession,
                    "primary_document": recent["primaryDocument"][i],
                    "accession_no_dashes": accession.replace("-", ""),
                }
            )
            if len(filings) >= num:
                break
        return filings

    def _download_primary_doc(self, cik: int, filing: dict, ticker: str) -> str:
        url = f"{ARCHIVES_BASE_URL.format(cik=cik, accession_no_dashes=filing['accession_no_dashes'])}/{filing['primary_document']}"
        resp = self._get(url)
        out_dir = self.data_dir / str(filing["fiscal_year"])
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{ticker.upper()}.htm"
        path.write_text(resp.text, encoding="utf-8")
        return str(path)

    def download_10k(self, ticker: str, num_filings: int = 2) -> list[dict]:
        cik = self._get_cik(ticker)
        filings = self._get_recent_10k_filings(cik, num_filings)
        if not filings:
            raise TickerNotFoundError(f"No 10-K filings found for {ticker}")
        results = []
        for filing in filings:
            path = self._download_primary_doc(cik, filing, ticker)
            results.append(
                {
                    "fiscal_year": filing["fiscal_year"],
                    "filing_date": filing["filing_date"],
                    "path": path,
                }
            )
        return results
