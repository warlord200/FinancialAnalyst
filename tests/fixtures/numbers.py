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

# Peer facts for the scorecard: deliberately different round numbers so a
# comparison is easy to check. F is richer and more profitable than TSLA
# (revenue 100 -> 300 over FY2020..FY2025, gross margin 40%, net margin
# 20%); GM is bigger but shrinking (revenue 500 -> 400, net margin 5%,
# current ratio below 1).
F_TABLE = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": {
        y: 100 + 40 * (y - 2020) for y in YEARS
    },
    "GrossProfit": {y: 0.40 * (100 + 40 * (y - 2020)) for y in YEARS},
    "OperatingIncomeLoss": {y: 0.25 * (100 + 40 * (y - 2020)) for y in YEARS},
    "NetIncomeLoss": {y: 0.20 * (100 + 40 * (y - 2020)) for y in YEARS},
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": {
        y: 1.3 * 0.20 * (100 + 40 * (y - 2020)) for y in YEARS
    },
    "IncomeTaxExpenseBenefit": {y: 0.3 * 0.20 * (100 + 40 * (y - 2020)) for y in YEARS},
    "Assets": {y: 400 for y in YEARS},
    "AssetsCurrent": {y: 200 for y in YEARS},
    "LiabilitiesCurrent": {y: 100 for y in YEARS},
    "Liabilities": {y: 200 for y in YEARS},
    "StockholdersEquity": {y: 200 for y in YEARS},
    "LongTermDebt": {y: 80 for y in YEARS},
    "LongTermDebtCurrent": {y: 20 for y in YEARS},
    "CashAndCashEquivalentsAtCarryingValue": {y: 50 for y in YEARS},
    "NetCashProvidedByUsedInOperatingActivities": {y: 60 for y in YEARS},
    "PaymentsToAcquirePropertyPlantAndEquipment": {y: 20 for y in YEARS},
}

GM_TABLE = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": {
        y: 500 - 20 * (y - 2020) for y in YEARS
    },
    "GrossProfit": {y: 0.30 * (500 - 20 * (y - 2020)) for y in YEARS},
    "OperatingIncomeLoss": {y: 0.10 * (500 - 20 * (y - 2020)) for y in YEARS},
    "NetIncomeLoss": {y: 0.05 * (500 - 20 * (y - 2020)) for y in YEARS},
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": {
        y: 1.3 * 0.05 * (500 - 20 * (y - 2020)) for y in YEARS
    },
    "IncomeTaxExpenseBenefit": {y: 0.3 * 0.05 * (500 - 20 * (y - 2020)) for y in YEARS},
    "Assets": {y: 1000 for y in YEARS},
    "AssetsCurrent": {y: 300 for y in YEARS},
    "LiabilitiesCurrent": {y: 400 for y in YEARS},
    "Liabilities": {y: 700 for y in YEARS},
    "StockholdersEquity": {y: 300 for y in YEARS},
    "LongTermDebt": {y: 300 for y in YEARS},
    "LongTermDebtCurrent": {y: 0 for y in YEARS},
    "CashAndCashEquivalentsAtCarryingValue": {y: 100 for y in YEARS},
    "NetCashProvidedByUsedInOperatingActivities": {y: 80 for y in YEARS},
    "PaymentsToAcquirePropertyPlantAndEquipment": {y: 30 for y in YEARS},
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


class ByCikFactsFetcher:
    """A facts fetcher that returns a different company-facts payload per
    CIK, so peer scorecard tests compare genuinely different numbers."""

    def __init__(self, by_cik):
        self.by_cik = by_cik
        self.calls = []

    def __call__(self, cik):
        self.calls.append(cik)
        return self.by_cik[cik]


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
