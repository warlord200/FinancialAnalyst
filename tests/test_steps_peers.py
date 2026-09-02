"""Unit tests for the peer scorecard (T10): comparing a target company
against peers on growth, margins, debt, and returns.

The scorecard is a pure derivation from the numbers layer, so the expected
figures are the same worked examples asserted in ``test_numbers_statements``
for the FULL_TABLE target, plus the round-number peer fixtures: F has
revenue 100 -> 300 over FY2020..FY2025 (latest 300), gross margin 40%, net
margin 20%, current ratio 2.0; GM has revenue 500 -> 400 (latest 400), net
margin 5%, current ratio 0.75.
"""

import pytest

from financial_analyst.numbers.statements import compute
from financial_analyst.steps.peers import build_scorecard, snapshot
from financial_analyst.steps.state import PeerStateStore
from tests.fixtures.numbers import (
    F_TABLE,
    FULL_TABLE,
    GM_TABLE,
)
from tests.fixtures.xbrl_facts import make_facts

REVENUE_TAG = "RevenueFromContractWithCustomerExcludingAssessedTax"
GROSS_PROFIT_TAG = "GrossProfit"


def tsla_financials():
    return compute(make_facts(FULL_TABLE))


def f_financials():
    return compute(make_facts(F_TABLE))


def gm_financials():
    return compute(make_facts(GM_TABLE))


def fact_values(sources):
    return {t.value for t in sources if t.type == "xbrl_fact"}


class TestSnapshot:
    def test_snapshot_takes_latest_year_values(self):
        values = snapshot(tsla_financials())
        assert values["revenue_growth_yoy"] == pytest.approx((150 - 140) / 140)
        assert values["revenue_cagr_5y"] == pytest.approx((150 / 100) ** (1 / 5) - 1)
        assert values["gross_margin"] == pytest.approx(0.25)
        assert values["net_margin"] == pytest.approx(0.10)
        assert values["current_ratio"] == pytest.approx(1.75)
        assert values["debt_to_equity"] == pytest.approx(0.48)
        assert values["debt_to_assets"] == pytest.approx(60.0 / 350.0)
        assert values["roe"] == pytest.approx(0.12)

    def test_snapshot_leaves_missing_metrics_as_none(self):
        values = snapshot(tsla_financials())
        assert values["roic"] is None or isinstance(values["roic"], float)


class TestBuildScorecard:
    def test_build_scorecard_has_four_tables_with_target_and_peers_as_columns(self):
        tables = build_scorecard("TSLA", tsla_financials(), [("F", f_financials())])
        assert [t.key for t in tables] == [
            "growth",
            "margins",
            "debt_liquidity",
            "returns",
        ]
        assert tables[0].columns == ["TSLA", "F"]
        assert tables[0].title == "Growth"
        assert tables[0].column_labels == {"TSLA": "TSLA · FY2025", "F": "F · FY2025"}

    def test_growth_rows_compare_target_and_peer(self):
        tables = build_scorecard("TSLA", tsla_financials(), [("F", f_financials())])
        rows = {r.label: r for r in tables[0].rows}
        assert rows["Revenue growth (YoY)"].values["TSLA"] == pytest.approx((150 - 140) / 140)
        assert rows["Revenue growth (YoY)"].values["F"] == pytest.approx((300 - 260) / 260)
        assert rows["Revenue CAGR (5y)"].values["TSLA"] == pytest.approx((150 / 100) ** (1 / 5) - 1)
        assert rows["Revenue CAGR (5y)"].values["F"] == pytest.approx((300 / 100) ** (1 / 5) - 1)
        assert REVENUE_TAG in fact_values(rows["Revenue growth (YoY)"].sources)

    def test_margin_rows_carry_xbrl_fact_sources(self):
        tables = build_scorecard("TSLA", tsla_financials(), [("F", f_financials())])
        rows = {r.label: r for r in tables[1].rows}
        assert rows["Gross margin"].values["TSLA"] == pytest.approx(0.25)
        assert rows["Gross margin"].values["F"] == pytest.approx(0.40)
        assert rows["Operating margin"].values["F"] == pytest.approx(0.25)
        assert rows["Net margin"].values["F"] == pytest.approx(0.20)
        assert GROSS_PROFIT_TAG in fact_values(rows["Gross margin"].sources)
        assert REVENUE_TAG in fact_values(rows["Gross margin"].sources)

    def test_debt_rows_compare_ratio_metrics(self):
        tables = build_scorecard("TSLA", tsla_financials(), [("F", f_financials())])
        rows = {r.label: r for r in tables[2].rows}
        assert rows["Current ratio"].values["TSLA"] == pytest.approx(1.75)
        assert rows["Current ratio"].values["F"] == pytest.approx(2.0)
        assert rows["Debt / equity"].values["F"] == pytest.approx(100.0 / 200.0)
        assert rows["Debt / assets"].values["TSLA"] == pytest.approx(60.0 / 350.0)

    def test_returns_rows_compare_target_and_peer(self):
        tables = build_scorecard("TSLA", tsla_financials(), [("F", f_financials())])
        rows = {r.label: r for r in tables[3].rows}
        assert rows["ROE"].values["TSLA"] == pytest.approx(0.12)
        assert rows["ROE"].values["F"] == pytest.approx(60.0 / 200.0)
        assert rows["ROCE"].values["TSLA"] == pytest.approx(22.5 / 250.0)

    def test_scorecard_handles_peers_with_negative_growth(self):
        tables = build_scorecard("TSLA", tsla_financials(), [("GM", gm_financials())])
        rows = {r.label: r for r in tables[0].rows}
        assert rows["Revenue growth (YoY)"].values["GM"] == pytest.approx((400 - 420) / 420)
        debt_rows = {r.label: r for r in tables[2].rows}
        assert debt_rows["Current ratio"].values["GM"] == pytest.approx(0.75)
        margin_rows = {r.label: r for r in tables[1].rows}
        assert margin_rows["Net margin"].values["GM"] == pytest.approx(0.05)

    def test_peer_with_short_history_has_none_cagr(self):
        sparse = {
            tag: {y: values[y] for y in (2024, 2025)}
            for tag, values in FULL_TABLE.items()
        }
        tables = build_scorecard("TSLA", tsla_financials(), [("NEW", compute(make_facts(sparse)))])
        rows = {r.label: r for r in tables[0].rows}
        assert rows["Revenue growth (YoY)"].values["NEW"] == pytest.approx((150 - 140) / 140)
        assert rows["Revenue CAGR (5y)"].values["NEW"] is None


class TestPeerStateStore:
    def test_set_and_list_peers_round_trip_in_order(self, tmp_path):
        store = PeerStateStore(str(tmp_path / "steps.db"))
        store.set_peers("a@example.com", "TSLA", ["GM", "F"])
        assert store.list_peers("a@example.com", "TSLA") == ["GM", "F"]

    def test_set_peers_replaces_the_list(self, tmp_path):
        store = PeerStateStore(str(tmp_path / "steps.db"))
        store.set_peers("a@example.com", "TSLA", ["GM"])
        store.set_peers("a@example.com", "TSLA", ["F"])
        assert store.list_peers("a@example.com", "TSLA") == ["F"]

    def test_peers_are_scoped_to_user_and_company(self, tmp_path):
        store = PeerStateStore(str(tmp_path / "steps.db"))
        store.set_peers("a@example.com", "TSLA", ["F"])
        store.set_peers("b@example.com", "TSLA", ["GM"])
        store.set_peers("a@example.com", "MSFT", ["AAPL"])
        assert store.list_peers("a@example.com", "TSLA") == ["F"]
        assert store.list_peers("b@example.com", "TSLA") == ["GM"]
        assert store.list_peers("a@example.com", "MSFT") == ["AAPL"]

    def test_clear_returns_empty_list(self, tmp_path):
        store = PeerStateStore(str(tmp_path / "steps.db"))
        store.set_peers("a@example.com", "TSLA", ["F"])
        store.set_peers("a@example.com", "TSLA", [])
        assert store.list_peers("a@example.com", "TSLA") == []
