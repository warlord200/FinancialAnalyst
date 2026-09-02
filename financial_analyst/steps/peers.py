"""Step 3 peer scorecard (T10): compare a company against user-chosen peers.

The scorecard is a pure derivation from the numbers layer, exactly like the
computed tables in ``financial_analyst.steps.financials``: no LLM is
involved, so every figure is grounded by construction in the raw XBRL
company-facts data. Each metric row carries ``xbrl_fact`` source tags
pointing at the us-gaap concepts the row is derived from.

Columns are companies (the target first, then each peer), not fiscal years:
peers rarely share the target's fiscal year, so every cell is that company's
latest-year value for the metric. The ``column_labels`` on each table show
which fiscal year each column draws on.
"""

from financial_analyst.steps.financials import (
    RATIO_FACTS,
    RATIO_LABELS,
    FinancialTable,
    TableRow,
    fact_tags,
)

GROWTH_FACTS = (("income_statement", "revenue"),)

# Each group is (table key, title, unit, metrics).
SCORECARD_TABLES = (
    ("growth", "Growth", "percent", ("revenue_growth_yoy", "revenue_cagr_5y")),
    (
        "margins",
        "Margins",
        "percent",
        ("gross_margin", "operating_margin", "net_margin"),
    ),
    (
        "debt_liquidity",
        "Debt & liquidity",
        "ratio",
        ("current_ratio", "debt_to_equity", "debt_to_assets"),
    ),
    ("returns", "Returns", "percent", ("roe", "roce", "roic")),
)

ROW_LABELS = {
    "revenue_growth_yoy": "Revenue growth (YoY)",
    "revenue_cagr_5y": "Revenue CAGR (5y)",
    **RATIO_LABELS,
}


def _latest_value(series: dict[str, float]) -> float | None:
    if not series:
        return None
    year = max(int(y) for y in series)
    return series[str(year)]


def _yoy_growth(values: dict[str, float]) -> float | None:
    years = sorted(int(y) for y in values)
    if len(years) < 2:
        return None
    latest, prior = years[-1], years[-2]
    prior_value = values[str(prior)]
    if not prior_value:
        return None
    return (values[str(latest)] - prior_value) / prior_value


def _fact_pairs(metric: str) -> tuple[tuple[str, str], ...]:
    if metric in RATIO_FACTS:
        return RATIO_FACTS[metric]
    if metric in ("revenue_growth_yoy", "revenue_cagr_5y"):
        return GROWTH_FACTS
    return ()


def snapshot(financials: dict) -> dict[str, float | None]:
    """The latest-year metric values for one company, as a flat dict keyed
    by metric name."""
    ratios = financials.get("ratios", {})
    cagr = financials.get("cagr", {})
    revenue = financials.get("income_statement", {}).get("revenue", {})
    values: dict[str, float | None] = {
        "revenue_growth_yoy": _yoy_growth(revenue),
        "revenue_cagr_5y": cagr.get("revenue", {}).get("5"),
    }
    for metric in RATIO_FACTS:
        values[metric] = _latest_value(ratios.get(metric, {}))
    return values


def _latest_fiscal_year(financials: dict) -> int | None:
    years = financials.get("fiscal_years", [])
    return years[0] if years else None


def build_scorecard(
    target_ticker: str,
    target_financials: dict,
    peers: list[tuple[str, dict]],
) -> list[FinancialTable]:
    """Compare the target against each peer's latest-year figures.

    ``peers`` is a list of ``(ticker, financials)`` pairs kept in the order
    given. The returned tables share the FinancialTable shape used by the
    financials step, so the frontend renders them with the same table
    component.
    """
    companies = [(target_ticker, target_financials)] + [
        (ticker, financials) for ticker, financials in peers if financials
    ]
    tickers = [ticker for ticker, _ in companies]
    column_labels = {}
    for ticker, financials in companies:
        year = _latest_fiscal_year(financials)
        column_labels[ticker] = f"{ticker} · FY{year}" if year else ticker
    snapshots = {ticker: snapshot(financials) for ticker, financials in companies}

    tables: list[FinancialTable] = []
    for key, title, unit, metrics in SCORECARD_TABLES:
        rows = []
        for metric in metrics:
            pairs = _fact_pairs(metric)
            rows.append(
                TableRow(
                    label=ROW_LABELS.get(metric, metric),
                    values={ticker: snapshots[ticker].get(metric) for ticker in tickers},
                    sources=fact_tags(pairs),
                )
            )
        tables.append(
            FinancialTable(
                key=key,
                title=title,
                columns=tickers,
                column_labels=column_labels,
                rows=rows,
                unit=unit,
            )
        )
    return tables
