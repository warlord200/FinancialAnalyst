"""Step 1: the one-pager.

A pure derivation from the numbers layer. Revenue growth, profitability,
and debt come straight out of the computed XBRL figures, and the bull/bear
tag is a small rule-based score over the latest numbers — no LLM, so every
figure is grounded by construction in the raw company-facts data.

Tag rules (product decision, deliberately transparent): 2 points when the
latest figure is strong (5y revenue CAGR >= 10%, net margin >= 15%, debt to
assets <= 30%), 1 point when acceptable (CAGR/margin >= 0, debt to assets
<= 60%), 0 otherwise. Sum of three axes out of 6: >= 5 bullish, 3-4
neutral, <= 2 bearish.
"""

MAX_TAG_POINTS = 6


def _latest(series: dict[str, float]) -> tuple[str | None, float | None]:
    if not series:
        return None, None
    year = max(int(y) for y in series)
    return str(year), series[str(year)]


def _yoy_growth(values: dict[str, float]) -> float | None:
    years = sorted(int(y) for y in values)
    if len(years) < 2:
        return None
    latest, prior = years[-1], years[-2]
    prior_value = values[str(prior)]
    if not prior_value:
        return None
    return (values[str(latest)] - prior_value) / prior_value


def _higher_points(value: float | None, good: float, ok: float) -> int:
    if value is None:
        return 0
    if value >= good:
        return 2
    if value >= ok:
        return 1
    return 0


def _lower_points(value: float | None, good: float, ok: float) -> int:
    if value is None:
        return 0
    if value <= good:
        return 2
    if value <= ok:
        return 1
    return 0


def _pct_line(value: float | None, label: str) -> str:
    if value is None:
        return f"{label} n/a"
    return f"{label} {value * 100:.1f}%"


def _tag(cagr_5y: float | None, net_margin: float | None, debt_to_assets: float | None) -> dict:
    points = (
        _higher_points(cagr_5y, good=0.10, ok=0.0)
        + _higher_points(net_margin, good=0.15, ok=0.0)
        + _lower_points(debt_to_assets, good=0.30, ok=0.60)
    )
    if points >= 5:
        label = "bullish"
    elif points >= 3:
        label = "neutral"
    else:
        label = "bearish"
    rationale = "; ".join(
        [
            _pct_line(cagr_5y, "5y revenue CAGR"),
            _pct_line(net_margin, "net margin"),
            _pct_line(debt_to_assets, "debt/assets"),
        ]
    )
    return {
        "label": label,
        "score": round(points / MAX_TAG_POINTS * 100),
        "rationale": f"{rationale} -> {label}",
    }


def build_one_pager(financials: dict) -> dict:
    ratios = financials.get("ratios", {})
    cagr = financials.get("cagr", {})
    income = financials.get("income_statement", {})

    latest_year, latest_revenue = _latest(income.get("revenue", {}))
    revenue_cagr_5y = cagr.get("revenue", {}).get("5")
    _, net_margin = _latest(ratios.get("net_margin", {}))
    _, debt_to_assets = _latest(ratios.get("debt_to_assets", {}))

    return {
        "latest_fiscal_year": int(latest_year) if latest_year else None,
        "source": "SEC XBRL company-facts (us-gaap)",
        "growth": {
            "latest_revenue": latest_revenue,
            "revenue_growth_yoy": _yoy_growth(income.get("revenue", {})),
            "revenue_cagr_5y": revenue_cagr_5y,
        },
        "profitability": {
            "gross_margin": _latest(ratios.get("gross_margin", {}))[1],
            "operating_margin": _latest(ratios.get("operating_margin", {}))[1],
            "net_margin": net_margin,
        },
        "debt": {
            "debt_to_assets": debt_to_assets,
            "debt_to_equity": _latest(ratios.get("debt_to_equity", {}))[1],
        },
        "tag": _tag(revenue_cagr_5y, net_margin, debt_to_assets),
    }
