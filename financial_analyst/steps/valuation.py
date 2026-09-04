"""Step 5: Valuation.

A pure derivation from the numbers layer, exactly like the peer scorecard:
no LLM and no corpus, so every figure is grounded by construction in the raw
XBRL company-facts data. The user corrects a price through the numbers layer
override and this module recomputes on demand.

Outputs, all numbers:

- ``dcf`` — a single-stage growing-perpetuity DCF on the latest free cash
  flow, with overridable discount rate and growth assumptions and a
  sensitivity grid over both. Equity value per share is the present value of
  the growing FCF stream minus net debt, divided by shares outstanding. The
  model is deliberately transparent: ``FCF_1 / (r - g) - net_debt`` over
  shares. It is ``None`` when the base-year FCF is missing or not positive.
- ``multiples`` — trailing market multiples at the current price: P/E,
  EV/EBITDA, and FCF yield, with the inputs (market cap, EV, EPS, EBITDA,
  FCF) so the numbers are auditable. P/E uses EPS = net income / weighted
  average diluted shares; EV adds net debt to market cap, where market cap
  uses point-in-time shares outstanding. EV/EBITDA uses EBITDA =
  operating income + D&A when the company reports D&A, else it is not
  derivable and stays ``None``.
- ``history`` — the same multiples per past fiscal year, with the price
  aligned to each year's actual fiscal-year end date (from the numbers-layer
  ``fiscal_year_ends`` map), so non-calendar year-end companies align
  correctly.
"""

DEFAULT_DISCOUNT_RATE = 0.10
DEFAULT_GROWTH = 0.03

SENSITIVITY_DISCOUNT_RATES = [0.08, 0.09, 0.10, 0.11, 0.12]
SENSITIVITY_GROWTH_RATES = [0.02, 0.025, 0.03, 0.035, 0.04]


def _latest_fiscal_year(financials: dict) -> int | None:
    years = financials.get("fiscal_years", [])
    return years[0] if years else None


def _line(financials: dict, section: str, name: str) -> dict[str, float]:
    return financials.get(section, {}).get(name, {})


def _at_year(financials: dict, section: str, name: str, year: int) -> float | None:
    return _line(financials, section, name).get(str(year))


def _share_count(
    shares: dict, preferred: str, fallback: str, year: int
) -> float | None:
    """The share count for a fiscal year, from the preferred series with the
    fallback used only when the preferred series lacks that year."""
    series = shares.get(preferred, {})
    if str(year) not in series:
        series = shares.get(fallback, {})
    return series.get(str(year))


def _shares_for_cap(shares: dict, year: int) -> float | None:
    return _share_count(shares, "outstanding", "weighted_average_diluted", year)


def _shares_for_eps(shares: dict, year: int) -> float | None:
    return _share_count(shares, "weighted_average_diluted", "outstanding", year)


def _net_debt(financials: dict, year: int) -> float:
    long_term = _at_year(financials, "balance_sheet", "long_term_debt", year) or 0.0
    current = _at_year(financials, "balance_sheet", "long_term_debt_current", year) or 0.0
    cash = _at_year(financials, "balance_sheet", "cash_and_equivalents", year) or 0.0
    return long_term + current - cash


def _free_cash_flow(financials: dict, year: int) -> float | None:
    ocf = _at_year(financials, "cash_flow", "operating_cash_flow", year)
    capex = _at_year(financials, "cash_flow", "capital_expenditure", year)
    if ocf is None or capex is None:
        return None
    return ocf - capex


def _ebitda(financials: dict, year: int) -> float | None:
    operating_income = _at_year(financials, "income_statement", "operating_income", year)
    da = financials.get("depreciation_amortization", {}).get(str(year))
    if operating_income is None:
        return None
    if da is None:
        return None
    return operating_income + da


def _multiples_at(financials: dict, year: int, price: float | None) -> dict:
    shares = financials.get("shares", {})
    net_income = _at_year(financials, "income_statement", "net_income", year)

    cap_shares = _shares_for_cap(shares, year)
    eps_shares = _shares_for_eps(shares, year)
    market_cap = price * cap_shares if price is not None and cap_shares else None
    net_debt = _net_debt(financials, year)
    enterprise_value = (
        market_cap + net_debt if market_cap is not None else None
    )
    eps = net_income / eps_shares if net_income is not None and eps_shares else None
    fcf = _free_cash_flow(financials, year)
    ebitda = _ebitda(financials, year)

    pe = price / eps if price is not None and eps and eps > 0 else None
    ev_ebitda = (
        enterprise_value / ebitda
        if enterprise_value is not None and ebitda and ebitda > 0
        else None
    )
    fcf_yield = (
        fcf / market_cap if fcf is not None and market_cap and market_cap > 0 else None
    )
    return {
        "price": price,
        "market_cap": market_cap,
        "enterprise_value": enterprise_value,
        "net_debt": net_debt,
        "eps": eps,
        "pe": pe,
        "ebitda": ebitda,
        "ev_ebitda": ev_ebitda,
        "fcf": fcf,
        "fcf_yield": fcf_yield,
    }


def market_multiples(financials: dict, price: float | None) -> dict:
    """Trailing multiples at ``price`` for the company's latest fiscal year."""
    year = _latest_fiscal_year(financials)
    if year is None:
        return {"price": price, "fiscal_year": None}
    return {"fiscal_year": year, **_multiples_at(financials, year, price)}


def _dcf_components(
    financials: dict, year: int, discount_rate: float, growth: float
) -> dict | None:
    """The DCF breakdown for a fiscal year, or None when the company cannot
    be valued.

    A single-stage growing perpetuity on the year's free cash flow. Returns
    None only when the company itself cannot be valued — the free cash flow
    is missing or not positive, or there are no shares to divide by. A
    discount rate that does not exceed the growth rate (the perpetuity
    diverges) is an assumption problem, not a company-data problem: the
    payload is returned with ``enterprise_value``, ``equity_value`` and
    ``equity_value_per_share`` nulled and ``diverges`` set, so the caller can
    keep the model visible and let the user correct the assumptions.
    """
    fcf = _free_cash_flow(financials, year)
    cap_shares = _shares_for_cap(financials.get("shares", {}), year)
    if fcf is None or fcf <= 0 or not cap_shares:
        return None
    net_debt = _net_debt(financials, year)
    if discount_rate <= growth:
        return {
            "fcf": fcf,
            "net_debt": net_debt,
            "enterprise_value": None,
            "equity_value": None,
            "equity_value_per_share": None,
            "diverges": True,
        }
    enterprise_value = fcf * (1 + growth) / (discount_rate - growth)
    equity_value = enterprise_value - net_debt
    return {
        "fcf": fcf,
        "net_debt": net_debt,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "equity_value_per_share": equity_value / cap_shares,
        "diverges": False,
    }


def _dcf_sensitivity(
    financials: dict, year: int
) -> dict:
    rows = []
    for discount_rate in SENSITIVITY_DISCOUNT_RATES:
        values = {}
        for growth in SENSITIVITY_GROWTH_RATES:
            components = _dcf_components(financials, year, discount_rate, growth)
            values[f"{growth:.4g}"] = (
                components["equity_value_per_share"] if components else None
            )
        rows.append({"discount_rate": discount_rate, "values": values})
    return {
        "discount_rates": SENSITIVITY_DISCOUNT_RATES,
        "growth_rates": SENSITIVITY_GROWTH_RATES,
        "rows": rows,
    }


def dcf(
    financials: dict,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
    growth: float = DEFAULT_GROWTH,
) -> dict | None:
    """DCF equity value per share under single-stage growing perpetuity.

    Returns None when the company cannot be valued: the base-year free cash
    flow is missing or not positive, or there are no shares to divide by.
    When only the assumptions diverge (growth at or above the discount rate)
    the payload is still returned with the per-share value nulled, so the
    caller can keep the model on screen.
    """
    year = _latest_fiscal_year(financials)
    if year is None:
        return None
    components = _dcf_components(financials, year, discount_rate, growth)
    if components is None:
        return None
    return {
        "base_fiscal_year": str(year),
        "discount_rate": discount_rate,
        "growth": growth,
        **components,
        "sensitivity": _dcf_sensitivity(financials, year),
    }


def _price_on_or_before(history: list[dict], date: str) -> float | None:
    closest = None
    for row in history:
        if row["date"] <= date:
            closest = row["close"]
    return closest


def historical(financials: dict, history: list[dict]) -> list[dict]:
    """Per-fiscal-year market multiples, price aligned to each year's end."""
    ends = financials.get("fiscal_year_ends", {})
    rows = []
    for year in sorted(int(y) for y in ends):
        price = _price_on_or_before(history, ends[str(year)])
        if price is None:
            continue
        rows.append(
            {
                "fiscal_year": year,
                "end_date": ends[str(year)],
                **_multiples_at(financials, year, price),
            }
        )
    return rows


def valuation(
    financials: dict,
    price: float | None,
    history: list[dict],
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
    growth: float = DEFAULT_GROWTH,
) -> dict:
    """The full Step 5 payload: DCF, current multiples, and history."""
    return {
        "dcf": dcf(financials, discount_rate=discount_rate, growth=growth),
        "multiples": market_multiples(financials, price),
        "history": historical(financials, history),
    }
