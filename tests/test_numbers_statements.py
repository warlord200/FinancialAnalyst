import pytest

from financial_analyst.numbers.statements import compute
from tests.fixtures.xbrl_facts import make_facts

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


def test_compute_builds_multi_year_income_statement():
    result = compute(make_facts(FULL_TABLE))
    assert result["fiscal_years"] == list(reversed(YEARS))
    income = result["income_statement"]
    assert income["revenue"]["2025"] == 150.0
    assert income["gross_profit"]["2025"] == 37.5
    assert income["operating_income"]["2025"] == 22.5
    assert income["net_income"]["2025"] == 15.0
    assert income["revenue"]["2020"] == 100.0


def test_compute_builds_balance_sheet_and_cash_flow():
    result = compute(make_facts(FULL_TABLE))
    bs = result["balance_sheet"]
    assert bs["total_assets"]["2025"] == 350.0
    assert bs["current_assets"]["2025"] == 175.0
    assert bs["current_liabilities"]["2025"] == 100.0
    assert bs["total_liabilities"]["2025"] == 225.0
    assert bs["stockholders_equity"]["2025"] == 125.0
    cf = result["cash_flow"]
    assert cf["operating_cash_flow"]["2025"] == 40.0
    assert cf["capital_expenditure"]["2025"] == 12.0


def test_compute_common_size_statements():
    result = compute(make_facts(FULL_TABLE))
    common_income = result["common_size"]["income_statement"]
    assert common_income["gross_profit"]["2025"] == pytest.approx(0.25)
    assert common_income["operating_income"]["2025"] == pytest.approx(0.15)
    assert common_income["net_income"]["2025"] == pytest.approx(0.10)
    common_balance = result["common_size"]["balance_sheet"]
    assert common_balance["current_assets"]["2025"] == pytest.approx(0.5)
    assert common_balance["total_liabilities"]["2025"] == pytest.approx(225.0 / 350.0)
    assert common_balance["stockholders_equity"]["2025"] == pytest.approx(125.0 / 350.0)


def test_compute_ratios_known_values():
    result = compute(make_facts(FULL_TABLE))
    ratios = result["ratios"]
    assert ratios["gross_margin"]["2025"] == pytest.approx(0.25)
    assert ratios["operating_margin"]["2025"] == pytest.approx(0.15)
    assert ratios["net_margin"]["2025"] == pytest.approx(0.10)
    assert ratios["current_ratio"]["2025"] == pytest.approx(1.75)
    assert ratios["debt_to_equity"]["2025"] == pytest.approx(0.48)
    assert ratios["debt_to_assets"]["2025"] == pytest.approx(60.0 / 350.0)
    assert ratios["roe"]["2025"] == pytest.approx(0.12)
    assert ratios["roce"]["2025"] == pytest.approx(22.5 / 250.0)
    assert ratios["roic"]["2025"] == pytest.approx(
        22.5 * (1 - 4.5 / 19.5) / (60 + 125 - 20)
    )


def test_compute_5_year_cagr():
    result = compute(make_facts(FULL_TABLE))
    expected = (150.0 / 100.0) ** (1 / 5) - 1
    assert result["cagr"]["revenue"]["5"] == pytest.approx(expected)
    assert result["cagr"]["net_income"]["5"] == pytest.approx(expected)


def test_compute_10_and_15_year_cagr():
    years = list(range(2010, 2026))
    revenue = {y: 100 * 1.1 ** (y - 2010) for y in years}
    net_income = {y: 10 * 1.08 ** (y - 2010) for y in years}
    table = {
        "RevenueFromContractWithCustomerExcludingAssessedTax": revenue,
        "NetIncomeLoss": net_income,
    }
    result = compute(make_facts(table))
    cagr = result["cagr"]
    assert cagr["revenue"]["5"] == pytest.approx(0.10, abs=1e-9)
    assert cagr["revenue"]["10"] == pytest.approx(0.10, abs=1e-9)
    assert cagr["revenue"]["15"] == pytest.approx(0.10, abs=1e-9)
    assert cagr["net_income"]["5"] == pytest.approx(0.08, abs=1e-9)
    assert cagr["net_income"]["10"] == pytest.approx(0.08, abs=1e-9)
    assert cagr["net_income"]["15"] == pytest.approx(0.08, abs=1e-9)


def test_compute_tolerates_missing_concepts():
    facts = make_facts({"RevenueFromContractWithCustomerExcludingAssessedTax": REV})
    result = compute(facts)
    assert result["fiscal_years"] == list(reversed(YEARS))
    assert "ratios" not in result or result["ratios"] == {}


def test_compute_empty_facts():
    result = compute(make_facts({}))
    assert result == {
        "fiscal_years": [],
        "income_statement": {},
        "balance_sheet": {},
        "cash_flow": {},
        "common_size": {"income_statement": {}, "balance_sheet": {}},
        "ratios": {},
        "cagr": {},
    }
