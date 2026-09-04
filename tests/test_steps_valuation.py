"""Unit tests for the Step 5 valuation module (T11).

The valuation module is a pure derivation from the numbers layer (exactly
like the peer scorecard): no LLM, no corpus. Worked figures come from the
FULL_TABLE target: FY2025 revenue 150, net income 15 (EPS 1.5 on 10 shares),
operating income 22.5 + D&A 5 = EBITDA 27.5, FCF = OCF 40 - capex 12 = 28,
debt 60, cash 20. At a $25 price that gives market cap 250, EV 290,
P/E 16.67, EV/EBITDA 10.55, FCF yield 11.2%.

DCF (single-stage growing perpetuity) defaults: discount rate 10%, growth
3%. Equity per share = (FCF * (1+g) / (r-g) - net debt) / shares =
(28 * 1.03 / 0.07 - 40) / 10 = 37.20.
"""

import pytest

from financial_analyst.numbers.statements import compute
from financial_analyst.steps.valuation import dcf, historical, market_multiples, valuation
from tests.fixtures.numbers import FULL_TABLE
from tests.fixtures.xbrl_facts import make_facts

PRICE = 25.0

HISTORY = [
    {"date": "2021-12-31", "close": 20.0},
    {"date": "2022-12-30", "close": 30.0},
    {"date": "2023-12-29", "close": 40.0},
    {"date": "2024-12-31", "close": 30.0},
    {"date": "2025-12-31", "close": 25.0},
]


def full_financials():
    return compute(make_facts(FULL_TABLE))


class TestMarketMultiples:
    def test_market_multiples_at_current_price(self):
        m = market_multiples(full_financials(), PRICE)
        assert m["price"] == PRICE
        assert m["market_cap"] == pytest.approx(250.0)
        assert m["enterprise_value"] == pytest.approx(290.0)
        assert m["pe"] == pytest.approx(PRICE / 1.5)
        assert m["ev_ebitda"] == pytest.approx(290.0 / 27.5)
        assert m["fcf_yield"] == pytest.approx(28.0 / 250.0)

    def test_market_multiples_without_price_are_null(self):
        m = market_multiples(full_financials(), None)
        assert m["price"] is None
        assert m["pe"] is None
        assert m["ev_ebitda"] is None
        assert m["fcf_yield"] is None

    def test_market_multiples_use_latest_fiscal_year(self):
        m = market_multiples(full_financials(), PRICE)
        assert m["fiscal_year"] == 2025

    def test_negative_earnings_give_null_pe_but_real_ev_ebitda(self):
        financials = compute(make_facts(_losing_table()))
        m = market_multiples(financials, PRICE)
        assert m["pe"] is None
        assert m["ev_ebitda"] == pytest.approx(290.0 / 27.5)


class TestDcf:
    def test_dcf_defaults_single_stage_gordon(self):
        d = dcf(full_financials())
        assert d is not None
        assert d["base_fiscal_year"] == "2025"
        assert d["fcf"] == pytest.approx(28.0)
        assert d["discount_rate"] == pytest.approx(0.10)
        assert d["growth"] == pytest.approx(0.03)
        assert d["net_debt"] == pytest.approx(40.0)
        assert d["equity_value_per_share"] == pytest.approx(37.20)

    def test_dcf_overridden_assumptions(self):
        d = dcf(full_financials(), discount_rate=0.12, growth=0.05)
        assert d["discount_rate"] == pytest.approx(0.12)
        assert d["growth"] == pytest.approx(0.05)
        assert d["equity_value_per_share"] == pytest.approx(38.0)

    def test_dcf_sensitivity_grid_cells(self):
        d = dcf(full_financials())
        grid = d["sensitivity"]
        rows = {row["discount_rate"]: row["values"] for row in grid["rows"]}
        assert rows[0.08]["0.02"] == pytest.approx(43.60)
        assert rows[0.12]["0.04"] == pytest.approx(32.40)
        assert rows[0.10]["0.03"] == pytest.approx(37.20)
        assert grid["discount_rates"] == [0.08, 0.09, 0.10, 0.11, 0.12]
        assert grid["growth_rates"] == [0.02, 0.025, 0.03, 0.035, 0.04]

    def test_dcf_is_none_when_fcf_missing_or_negative(self):
        no_cash_flow = {
            tag: values
            for tag, values in FULL_TABLE.items()
            if tag
            not in ("NetCashProvidedByUsedInOperatingActivities", "PaymentsToAcquirePropertyPlantAndEquipment")
        }
        assert dcf(compute(make_facts(no_cash_flow))) is None

    def test_dcf_growth_equal_to_discount_still_returns_payload(self):
        """Growth matching the discount rate diverges the perpetuity but the
        company is otherwise valuble: the payload survives so the UI keeps the
        intrinsic-value section and its assumption inputs visible, with the
        per-share value nulled out (regression: the whole section vanished).
        """
        d = dcf(full_financials(), discount_rate=0.10, growth=0.10)
        assert d is not None
        assert d["discount_rate"] == pytest.approx(0.10)
        assert d["growth"] == pytest.approx(0.10)
        assert d["fcf"] == pytest.approx(28.0)
        assert d["net_debt"] == pytest.approx(40.0)
        assert d["enterprise_value"] is None
        assert d["equity_value"] is None
        assert d["equity_value_per_share"] is None
        assert d["sensitivity"]["rows"]

    def test_dcf_growth_above_discount_still_returns_payload(self):
        d = dcf(full_financials(), discount_rate=0.10, growth=0.12)
        assert d is not None
        assert d["equity_value_per_share"] is None


class TestHistorical:
    def test_history_aligns_prices_to_fiscal_year_ends(self):
        rows = historical(full_financials(), HISTORY)
        assert [r["fiscal_year"] for r in rows] == [2021, 2022, 2023, 2024, 2025]
        latest = rows[-1]
        assert latest["price"] == pytest.approx(25.0)
        assert latest["pe"] == pytest.approx(25.0 / 1.5)
        assert latest["ev_ebitda"] == pytest.approx(290.0 / 27.5)
        fy2023 = rows[2]
        assert fy2023["price"] == pytest.approx(40.0)
        assert fy2023["pe"] == pytest.approx(40.0 / (13.0 / 10.0))

    def test_history_skips_years_with_no_prior_price(self):
        short_history = HISTORY[-3:]
        rows = historical(full_financials(), short_history)
        assert [r["fiscal_year"] for r in rows] == [2023, 2024, 2025]


class TestValuation:
    def test_valuation_combines_dcf_multiples_and_history(self):
        v = valuation(full_financials(), PRICE, HISTORY)
        assert set(v) == {"dcf", "multiples", "history"}
        assert v["dcf"]["equity_value_per_share"] == pytest.approx(37.20)
        assert v["multiples"]["pe"] == pytest.approx(PRICE / 1.5)
        assert v["history"][-1]["fiscal_year"] == 2025

    def test_valuation_overrides_flow_into_dcf(self):
        v = valuation(full_financials(), PRICE, HISTORY, discount_rate=0.12, growth=0.05)
        assert v["dcf"]["equity_value_per_share"] == pytest.approx(38.0)
        assert v["multiples"]["pe"] == pytest.approx(PRICE / 1.5)


def _losing_table():
    table = {
        tag: {y: values for y, values in series.items()}
        for tag, series in FULL_TABLE.items()
    }
    table["NetIncomeLoss"] = {y: -1.0 * v for y, v in table["NetIncomeLoss"].items()}
    table["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"] = {
        y: -1.0 * v for y, v in table["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"].items()
    }
    return table
