"""Step 3: the Financials artifact.

A hybrid step: the computed figures (common-size statements, margins,
liquidity/solvency ratios, returns, and CAGRs) come straight from the
numbers layer, so they are grounded by construction and carry ``xbrl_fact``
source tags pointing at the exact us-gaap concepts they are derived from.
The forensic note (related-party transactions, management compensation,
non-GAAP reliance) is drafted by the generation framework over Item 7 /
Item 8 (MD&A and the financial statements), so it is source-tagged like
any other drafted section.
"""

from typing import Literal

from pydantic import BaseModel, Field

from financial_analyst.numbers.statements import STATEMENT_LINES
from financial_analyst.steps.generation import Artifact, SectionSpec, SourceTag

ARTIFACT_TYPE = "financials"

LINE_LABELS = {
    "revenue": "Revenue",
    "gross_profit": "Gross profit",
    "operating_income": "Operating income",
    "net_income": "Net income",
    "income_before_tax": "Income before tax",
    "income_tax_expense": "Income tax expense",
    "total_assets": "Total assets",
    "current_assets": "Current assets",
    "current_liabilities": "Current liabilities",
    "total_liabilities": "Total liabilities",
    "stockholders_equity": "Stockholders' equity",
    "long_term_debt": "Long-term debt",
    "long_term_debt_current": "Long-term debt, current",
    "cash_and_equivalents": "Cash & equivalents",
}

RATIO_LABELS = {
    "gross_margin": "Gross margin",
    "operating_margin": "Operating margin",
    "net_margin": "Net margin",
    "current_ratio": "Current ratio",
    "debt_to_equity": "Debt / equity",
    "debt_to_assets": "Debt / assets",
    "roe": "ROE",
    "roce": "ROCE",
    "roic": "ROIC",
}

RATIO_FACTS = {
    "gross_margin": (
        ("income_statement", "gross_profit"),
        ("income_statement", "revenue"),
    ),
    "operating_margin": (
        ("income_statement", "operating_income"),
        ("income_statement", "revenue"),
    ),
    "net_margin": (
        ("income_statement", "net_income"),
        ("income_statement", "revenue"),
    ),
    "current_ratio": (
        ("balance_sheet", "current_assets"),
        ("balance_sheet", "current_liabilities"),
    ),
    "debt_to_equity": (
        ("balance_sheet", "long_term_debt"),
        ("balance_sheet", "long_term_debt_current"),
        ("balance_sheet", "stockholders_equity"),
    ),
    "debt_to_assets": (
        ("balance_sheet", "long_term_debt"),
        ("balance_sheet", "long_term_debt_current"),
        ("balance_sheet", "total_assets"),
    ),
    "roe": (
        ("income_statement", "net_income"),
        ("balance_sheet", "stockholders_equity"),
    ),
    "roce": (
        ("income_statement", "operating_income"),
        ("balance_sheet", "total_assets"),
        ("balance_sheet", "current_liabilities"),
    ),
    "roic": (
        ("income_statement", "operating_income"),
        ("income_statement", "income_before_tax"),
        ("income_statement", "income_tax_expense"),
        ("balance_sheet", "long_term_debt"),
        ("balance_sheet", "long_term_debt_current"),
        ("balance_sheet", "stockholders_equity"),
        ("balance_sheet", "cash_and_equivalents"),
    ),
}

CAGR_SPANS = ("5", "10", "15")

FINANCIALS_SECTIONS = (
    SectionSpec(
        key="forensic_related_parties",
        heading="Related-Party Transactions",
        query="What does the filing say about related-party transactions?",
        instruction=(
            "Cover only what the filing states. If the filing does not discuss "
            "related-party transactions, say so explicitly and cite the passage you "
            "relied on for that judgment."
        ),
        items=("ITEM 7", "ITEM 8"),
    ),
    SectionSpec(
        key="forensic_compensation",
        heading="Management Compensation",
        query="What does the filing say about management compensation?",
        instruction=(
            "Cover only what the filing states. Compensation detail usually lives in the "
            "proxy statement, not the 10-K financial statements; say clearly what the "
            "filing does and does not disclose, and cite the passage you relied on."
        ),
        items=("ITEM 7", "ITEM 8"),
    ),
    SectionSpec(
        key="forensic_non_gaap",
        heading="Non-GAAP Reliance",
        query=(
            "How does the filing present non-GAAP measures relative to GAAP, such as "
            "adjusted earnings or adjusted EBITDA, and how are they reconciled?"
        ),
        instruction=(
            "Cover only what the filing states about non-GAAP measures and their "
            "reconciliation to GAAP."
        ),
        items=("ITEM 7", "ITEM 8"),
    ),
)


class TableRow(BaseModel):
    label: str
    values: dict[str, float | None]
    sources: list[SourceTag] = Field(default_factory=list)


class FinancialTable(BaseModel):
    key: str
    title: str
    columns: list[str]
    rows: list[TableRow] = Field(default_factory=list)
    unit: Literal["percent", "ratio"]
    column_labels: dict[str, str] = Field(default_factory=dict)


class FinancialsArtifact(Artifact):
    tables: list[FinancialTable] = Field(default_factory=list)


def fact_tags(pairs: tuple[tuple[str, str], ...]) -> list[SourceTag]:
    tags = []
    for section, line in pairs:
        tags.extend(STATEMENT_LINES[section].get(line, []))
    return [SourceTag(type="xbrl_fact", value=tag) for tag in tags]


def _year_values(values: dict[str, float], columns: list[str]) -> dict[str, float | None]:
    return {col: values.get(col) for col in columns}


def _statement_table(
    key: str,
    title: str,
    section: str,
    statement: dict[str, dict[str, float]],
    columns: list[str],
) -> FinancialTable:
    rows = []
    for line, values in statement.items():
        rows.append(
            TableRow(
                label=LINE_LABELS.get(line, line),
                values=_year_values(values, columns),
                sources=fact_tags(((section, line),)),
            )
        )
    return FinancialTable(key=key, title=title, columns=columns, rows=rows, unit="percent")


def _ratio_table(
    key: str,
    title: str,
    ratios: dict[str, dict[str, float]],
    names: tuple[str, ...],
    unit: Literal["percent", "ratio"],
    columns: list[str],
) -> FinancialTable:
    rows = []
    for name in names:
        values = ratios.get(name, {})
        if not values:
            continue
        rows.append(
            TableRow(
                label=RATIO_LABELS.get(name, name),
                values=_year_values(values, columns),
                sources=fact_tags(RATIO_FACTS[name]),
            )
        )
    return FinancialTable(key=key, title=title, columns=columns, rows=rows, unit=unit)


def _cagr_table(cagr: dict[str, dict[str, float]]) -> FinancialTable:
    rows = []
    for line in ("revenue", "net_income"):
        values = cagr.get(line, {})
        if not values:
            continue
        rows.append(
            TableRow(
                label=LINE_LABELS.get(line, line),
                values=_year_values(values, list(CAGR_SPANS)),
                sources=fact_tags((("income_statement", line),)),
            )
        )
    return FinancialTable(
        key="cagr",
        title="CAGR (revenue & net income)",
        columns=list(CAGR_SPANS),
        column_labels={"5": "5y", "10": "10y", "15": "15y"},
        rows=rows,
        unit="percent",
    )


def build_tables(financials: dict) -> list[FinancialTable]:
    """Build the computed tables from the numbers layer output."""
    fiscal_years = [str(year) for year in financials.get("fiscal_years", [])]
    common_size = financials.get("common_size", {})
    ratios = financials.get("ratios", {})
    cagr = financials.get("cagr", {})

    tables = [
        _statement_table(
            "common_size_income",
            "Common-Size Income (% of revenue)",
            "income_statement",
            common_size.get("income_statement", {}),
            fiscal_years,
        ),
        _statement_table(
            "common_size_balance",
            "Common-Size Balance (% of assets)",
            "balance_sheet",
            common_size.get("balance_sheet", {}),
            fiscal_years,
        ),
        _ratio_table(
            "margins",
            "Margins",
            ratios,
            ("gross_margin", "operating_margin", "net_margin"),
            "percent",
            fiscal_years,
        ),
        _ratio_table(
            "liquidity_solvency",
            "Liquidity & Solvency",
            ratios,
            ("current_ratio", "debt_to_equity", "debt_to_assets"),
            "ratio",
            fiscal_years,
        ),
        _ratio_table(
            "returns",
            "Returns",
            ratios,
            ("roe", "roce", "roic"),
            "percent",
            fiscal_years,
        ),
        _cagr_table(cagr),
    ]
    return [table for table in tables if table.rows]


def build_financials(generator, ticker: str, financials: dict) -> FinancialsArtifact:
    """Draft the forensic note through the generation framework and combine it
    with the computed tables into the financials artifact."""
    drafted = generator.generate(ticker, ARTIFACT_TYPE, FINANCIALS_SECTIONS)
    return FinancialsArtifact(
        ticker=drafted.ticker,
        artifact_type=ARTIFACT_TYPE,
        fiscal_year=drafted.fiscal_year,
        scope=drafted.scope,
        generated_at=drafted.generated_at,
        sections=drafted.sections,
        tables=build_tables(financials),
    )
