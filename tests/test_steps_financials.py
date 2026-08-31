"""Unit tests for the Step 3 financials artifact: computed tables built from
the numbers layer with XBRL-fact citations, and the forensic note assembled
through the artifact generation framework.

Expected values are the same worked examples asserted in
``test_numbers_statements`` (round-number FULL_TABLE fixture), so the
assertions here are independent of the implementation: revenue 150 in
FY2025, gross margin 0.25, current ratio 1.75, ROE 0.12, 5y revenue CAGR
(150/100)**(1/5)-1.
"""

import pytest

from financial_analyst.numbers.statements import compute
from financial_analyst.steps.financials import (
    ARTIFACT_TYPE,
    FINANCIALS_SECTIONS,
    build_financials,
    build_tables,
)
from financial_analyst.steps.generation import ArtifactGenerator
from tests.fixtures.numbers import FULL_TABLE
from tests.fixtures.steps import (
    FakeLLM,
    FakeRetriever,
    make_financials_corpus,
    valid_financials_section_json,
)
from tests.fixtures.xbrl_facts import make_facts

REVENUE_TAG = "RevenueFromContractWithCustomerExcludingAssessedTax"
GROSS_PROFIT_TAG = "GrossProfit"
NET_INCOME_TAG = "NetIncomeLoss"


def financials_dict():
    return compute(make_facts(FULL_TABLE))


def table_by_key(tables, key):
    return next(t for t in tables if t.key == key)


def fact_values(sources):
    return {t.value for t in sources if t.type == "xbrl_fact"}


class TestBuildTables:
    def test_build_tables_renders_common_size_income_with_xbrl_citations(self):
        tables = build_tables(financials_dict())
        table = table_by_key(tables, "common_size_income")
        assert table.title == "Common-Size Income (% of revenue)"
        assert table.unit == "percent"
        assert table.columns[0] == "2025"
        rows = {r.label: r for r in table.rows}
        assert rows["Gross profit"].values["2025"] == pytest.approx(0.25)
        assert rows["Net income"].values["2025"] == pytest.approx(0.10)
        assert GROSS_PROFIT_TAG in fact_values(rows["Gross profit"].sources)
        assert REVENUE_TAG not in fact_values(rows["Gross profit"].sources)

    def test_build_tables_renders_common_size_balance(self):
        tables = build_tables(financials_dict())
        table = table_by_key(tables, "common_size_balance")
        rows = {r.label: r for r in table.rows}
        assert rows["Current assets"].values["2025"] == pytest.approx(0.5)
        assert rows["Total liabilities"].values["2025"] == pytest.approx(225.0 / 350.0)

    def test_build_tables_renders_margins_with_xbrl_citations(self):
        tables = build_tables(financials_dict())
        table = table_by_key(tables, "margins")
        rows = {r.label: r for r in table.rows}
        assert rows["Gross margin"].values["2025"] == pytest.approx(0.25)
        assert rows["Operating margin"].values["2025"] == pytest.approx(0.15)
        assert rows["Net margin"].values["2025"] == pytest.approx(0.10)
        assert GROSS_PROFIT_TAG in fact_values(rows["Gross margin"].sources)
        assert REVENUE_TAG in fact_values(rows["Gross margin"].sources)

    def test_build_tables_renders_liquidity_and_solvency(self):
        tables = build_tables(financials_dict())
        table = table_by_key(tables, "liquidity_solvency")
        assert table.unit == "ratio"
        rows = {r.label: r for r in table.rows}
        assert rows["Current ratio"].values["2025"] == pytest.approx(1.75)
        assert rows["Debt / equity"].values["2025"] == pytest.approx(0.48)
        assert rows["Debt / assets"].values["2025"] == pytest.approx(60.0 / 350.0)

    def test_build_tables_renders_returns(self):
        tables = build_tables(financials_dict())
        table = table_by_key(tables, "returns")
        rows = {r.label: r for r in table.rows}
        assert rows["ROE"].values["2025"] == pytest.approx(0.12)
        assert rows["ROCE"].values["2025"] == pytest.approx(22.5 / 250.0)

    def test_build_tables_renders_cagr_across_spans(self):
        tables = build_tables(financials_dict())
        table = table_by_key(tables, "cagr")
        assert table.columns == ["5", "10", "15"]
        assert table.column_labels == {"5": "5y", "10": "10y", "15": "15y"}
        rows = {r.label: r for r in table.rows}
        expected = (150.0 / 100.0) ** (1 / 5) - 1
        assert rows["Revenue"].values["5"] == pytest.approx(expected)
        assert rows["Net income"].values["5"] == pytest.approx(expected)
        assert REVENUE_TAG in fact_values(rows["Revenue"].sources)
        assert NET_INCOME_TAG in fact_values(rows["Net income"].sources)

    def test_build_tables_drops_empty_ratio_tables(self):
        sparse = compute(make_facts({"RevenueFromContractWithCustomerExcludingAssessedTax": {
            y: 100 for y in range(2020, 2026)
        }}))
        tables = build_tables(sparse)
        keys = {t.key for t in tables}
        assert "margins" not in keys
        assert "liquidity_solvency" not in keys
        assert "returns" not in keys
        assert "common_size_income" in keys


class TestBuildFinancials:
    def make_generator(self):
        return ArtifactGenerator(
            FakeRetriever(make_financials_corpus()),
            FakeLLM(valid_financials_section_json()),
        )

    def test_build_financials_combines_tables_and_forensic_sections(self):
        artifact = build_financials(self.make_generator(), "TSLA", financials_dict())
        assert artifact.artifact_type == ARTIFACT_TYPE
        assert artifact.ticker == "TSLA"
        assert artifact.fiscal_year == 2025
        assert artifact.scope.items == ["ITEM 7", "ITEM 8"]
        assert {t.key for t in artifact.tables} == {
            "common_size_income",
            "common_size_balance",
            "margins",
            "liquidity_solvency",
            "returns",
            "cagr",
        }

    def test_build_financials_drafts_three_forensic_areas(self):
        artifact = build_financials(self.make_generator(), "TSLA", financials_dict())
        keys = [s.key for s in artifact.sections]
        assert keys == [
            "forensic_related_parties",
            "forensic_compensation",
            "forensic_non_gaap",
        ]
        for section in artifact.sections:
            assert section.content
            assert len(section.sources) >= 1
            assert section.evidence

    def test_build_financials_forensic_specs_scope_to_item_7_and_8(self):
        items = set()
        for spec in FINANCIALS_SECTIONS:
            items.update(spec.items)
        assert items == {"ITEM 7", "ITEM 8"}
