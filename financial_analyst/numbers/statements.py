"""Derive multi-year statements, common-size figures, ratios, and CAGRs
from raw SEC XBRL company-facts data.

`compute` is a pure function of the raw company-facts JSON: the same input
always yields the same output, which is what makes every computed figure
reproducible from the raw XBRL data.
"""

from financial_analyst.numbers.xbrl import annual_values

REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
]
GROSS_PROFIT_TAGS = ["GrossProfit"]
OPERATING_INCOME_TAGS = ["OperatingIncomeLoss"]
NET_INCOME_TAGS = ["NetIncomeLoss"]
INCOME_BEFORE_TAX_TAGS = [
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
]
INCOME_TAX_TAGS = ["IncomeTaxExpenseBenefit"]
TOTAL_ASSETS_TAGS = ["Assets"]
CURRENT_ASSETS_TAGS = ["AssetsCurrent"]
CURRENT_LIABILITIES_TAGS = ["LiabilitiesCurrent"]
TOTAL_LIABILITIES_TAGS = ["Liabilities"]
EQUITY_TAGS = ["StockholdersEquity"]
LONG_TERM_DEBT_TAGS = ["LongTermDebt"]
LONG_TERM_DEBT_CURRENT_TAGS = ["LongTermDebtCurrent"]
CASH_TAGS = [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
]
OPERATING_CASH_FLOW_TAGS = ["NetCashProvidedByUsedInOperatingActivities"]
CAPEX_TAGS = ["PaymentsToAcquirePropertyPlantAndEquipment"]

STATEMENT_LINES = {
    "income_statement": {
        "revenue": REVENUE_TAGS,
        "gross_profit": GROSS_PROFIT_TAGS,
        "operating_income": OPERATING_INCOME_TAGS,
        "net_income": NET_INCOME_TAGS,
        "income_before_tax": INCOME_BEFORE_TAX_TAGS,
        "income_tax_expense": INCOME_TAX_TAGS,
    },
    "balance_sheet": {
        "total_assets": TOTAL_ASSETS_TAGS,
        "current_assets": CURRENT_ASSETS_TAGS,
        "current_liabilities": CURRENT_LIABILITIES_TAGS,
        "total_liabilities": TOTAL_LIABILITIES_TAGS,
        "stockholders_equity": EQUITY_TAGS,
        "long_term_debt": LONG_TERM_DEBT_TAGS,
        "long_term_debt_current": LONG_TERM_DEBT_CURRENT_TAGS,
        "cash_and_equivalents": CASH_TAGS,
    },
    "cash_flow": {
        "operating_cash_flow": OPERATING_CASH_FLOW_TAGS,
        "capital_expenditure": CAPEX_TAGS,
    },
}

CAGR_SPANS = [5, 10, 15]
CAGR_LINES = ["revenue", "net_income"]


def _str_year_map(values: dict[int, float]) -> dict[str, float]:
    return {str(fy): val for fy, val in sorted(values.items())}


def _compute_common_size(
    statement: dict[str, dict[str, float]], denominator: dict[str, float]
) -> dict[str, dict[str, float]]:
    return {
        line: _per_year(years, denominator) for line, years in statement.items()
    }


def _compute_ratios(
    income: dict[str, dict[str, float]],
    balance: dict[str, dict[str, float]],
    cash_flow: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    ratios: dict[str, dict[str, float]] = {}
    revenue = income.get("revenue", {})
    for name, numerator, denominator in [
        ("gross_margin", income.get("gross_profit", {}), revenue),
        ("operating_margin", income.get("operating_income", {}), revenue),
        ("net_margin", income.get("net_income", {}), revenue),
        ("current_ratio", balance.get("current_assets", {}), balance.get("current_liabilities", {})),
        ("debt_to_equity", _total_debt(balance), balance.get("stockholders_equity", {})),
        ("debt_to_assets", _total_debt(balance), balance.get("total_assets", {})),
        ("roe", income.get("net_income", {}), balance.get("stockholders_equity", {})),
    ]:
        ratios[name] = _per_year(numerator, denominator)

    roce = _per_year(
        income.get("operating_income", {}),
        _capital_employed(balance),
    )
    if roce:
        ratios["roce"] = roce

    roic = _compute_roic(income, balance)
    if roic:
        ratios["roic"] = roic
    return {name: values for name, values in ratios.items() if values}


def _per_year(numerator: dict[str, float], denominator: dict[str, float]) -> dict[str, float]:
    return {
        year: num / denominator[year]
        for year, num in numerator.items()
        if year in denominator and denominator[year]
    }


def _total_debt(balance: dict[str, dict[str, float]]) -> dict[str, float]:
    current = balance.get("long_term_debt_current", {})
    long_term = balance.get("long_term_debt", {})
    years = sorted(set(current) | set(long_term))
    return {
        year: current.get(year, 0.0) + long_term.get(year, 0.0) for year in years
    }


def _capital_employed(balance: dict[str, dict[str, float]]) -> dict[str, float]:
    assets = balance.get("total_assets", {})
    current_liabilities = balance.get("current_liabilities", {})
    return {
        year: assets[year] - current_liabilities[year]
        for year in assets
        if year in current_liabilities
    }


def _compute_roic(
    income: dict[str, dict[str, float]],
    balance: dict[str, dict[str, float]],
) -> dict[str, float]:
    before_tax = income.get("income_before_tax", {})
    tax_expense = income.get("income_tax_expense", {})
    operating_income = income.get("operating_income", {})
    equity = balance.get("stockholders_equity", {})
    cash = balance.get("cash_and_equivalents", {})
    debt = _total_debt(balance)

    years = sorted(
        set(operating_income)
        & set(equity)
        & set(cash)
        & set(debt)
    )
    result: dict[str, float] = {}
    for year in years:
        invested_capital = debt[year] + equity[year] - cash[year]
        if invested_capital <= 0:
            continue
        if year in before_tax and before_tax[year] and year in tax_expense:
            tax_rate = tax_expense[year] / before_tax[year]
        else:
            tax_rate = 0.21
        nopat = operating_income[year] * (1 - tax_rate)
        result[year] = nopat / invested_capital
    return result


def _compute_cagr(lines: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for line in CAGR_LINES:
        values = lines.get(line, {})
        if not values:
            continue
        years = sorted(int(year) for year in values)
        latest = years[-1]
        line_cagr: dict[str, float] = {}
        for span in CAGR_SPANS:
            start = latest - span
            start_str = str(start)
            if start_str not in values:
                continue
            end_value = values[str(latest)]
            start_value = values[start_str]
            if start_value <= 0 or end_value <= 0:
                continue
            line_cagr[str(span)] = (end_value / start_value) ** (1 / span) - 1
        if line_cagr:
            result[line] = line_cagr
    return result


def compute(company_facts: dict) -> dict:
    """Return a JSON-serializable dict of derived figures for the company."""
    statements: dict[str, dict[str, dict[str, float]]] = {}
    income = {}
    balance = {}
    cash_flow = {}
    for section, lines in STATEMENT_LINES.items():
        section_values: dict[str, dict[str, float]] = {}
        for name, tags in lines.items():
            values = annual_values(company_facts, tags)
            if values:
                section_values[name] = _str_year_map(values)
        statements[section] = section_values

    income = statements["income_statement"]
    balance = statements["balance_sheet"]
    cash_flow = statements["cash_flow"]

    fiscal_years: list[int] = []
    for section in statements.values():
        for values in section.values():
            for year_str in values:
                year = int(year_str)
                if year not in fiscal_years:
                    fiscal_years.append(year)
    fiscal_years.sort(reverse=True)

    common_size = {
        "income_statement": _compute_common_size(
            income, income.get("revenue", {})
        ),
        "balance_sheet": _compute_common_size(
            balance, balance.get("total_assets", {})
        ),
    }

    all_lines = {**income, **balance, **cash_flow}
    return {
        "fiscal_years": fiscal_years,
        "income_statement": income,
        "balance_sheet": balance,
        "cash_flow": cash_flow,
        "common_size": common_size,
        "ratios": _compute_ratios(income, balance, cash_flow),
        "cagr": _compute_cagr(all_lines),
    }
