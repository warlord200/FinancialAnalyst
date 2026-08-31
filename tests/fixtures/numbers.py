"""Shared test doubles for the numbers layer (FakeDownloader,
FakeFactsFetcher, FakePriceClient) and the round-number facts table.

The numbers follow deliberately round figures so computation assertions
can be checked against worked examples: revenue 100 -> 150 over FY2020..FY2025,
so the 5-year revenue CAGR is (150/100)**(1/5) - 1.
"""

from financial_analyst.ingestion.sec_downloader import TickerNotFoundError

YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
REV = {y: 100 + 10 * (y - 2020) for y in YEARS}

FULL_TABLE = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": REV,
    "GrossProfit": {y: 0.25 * REV[y] for y in YEARS},
    "OperatingIncomeLoss": {y: 0.15 * REV[y] for y in YEARS},
    "NetIncomeLoss": {y: 0.10 * REV[y] for y in YEARS},
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": {
        y: 1.3 * 0.10 * REV[y] for y in YEARS
    },
    "IncomeTaxExpenseBenefit": {y: 0.3 * 0.10 * REV[y] for y in YEARS},
    "Assets": {y: 300 + 10 * (y - 2020) for y in YEARS},
    "AssetsCurrent": {y: 150 + 5 * (y - 2020) for y in YEARS},
    "LiabilitiesCurrent": {y: 100 for y in YEARS},
    "Liabilities": {y: 200 + 5 * (y - 2020) for y in YEARS},
    "StockholdersEquity": {y: 100 + 5 * (y - 2020) for y in YEARS},
    "LongTermDebt": {y: 50 for y in YEARS},
    "LongTermDebtCurrent": {y: 10 for y in YEARS},
    "CashAndCashEquivalentsAtCarryingValue": {y: 20 for y in YEARS},
    "NetCashProvidedByUsedInOperatingActivities": {y: 30 + 2 * (y - 2020) for y in YEARS},
    "PaymentsToAcquirePropertyPlantAndEquipment": {y: 12 for y in YEARS},
}


class FakeDownloader:
    def __init__(self, ciks):
        self.ciks = ciks

    def validate_ticker(self, ticker):
        return ticker.upper() in self.ciks

    def get_cik(self, ticker):
        if ticker.upper() not in self.ciks:
            raise TickerNotFoundError(ticker)
        return self.ciks[ticker.upper()]


class FakeFactsFetcher:
    def __init__(self, facts):
        self.facts = facts
        self.calls = 0

    def __call__(self, cik):
        self.calls += 1
        return self.facts


class FakePriceClient:
    def __init__(self, current=253.4, history=None, error=None):
        self.current = current
        self.history = history or [{"date": "2026-08-29", "close": current}]
        self.error = error
        self.fetch_calls = 0

    def fetch_current(self, ticker):
        self.fetch_calls += 1
        if self.error:
            raise self.error
        return self.current

    def fetch_history(self, ticker):
        if self.error:
            raise self.error
        return self.history
