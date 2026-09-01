"""Unit tests for the Step 4 strategy artifact: the plan, capex, and
financing sections drafted through the generation framework, plus the
long-run returns table (ROIC / ROE / ROCE) built from the numbers layer
with XBRL-fact citations.

Expected values are the same worked examples asserted in
``test_numbers_statements`` (the round-number FULL_TABLE fixture), so ROE
0.12 and ROCE 22.5/250 in FY2025.
"""

import pytest

from financial_analyst.numbers.statements import compute
from financial_analyst.steps.generation import ArtifactGenerator
from financial_analyst.steps.strategy import (
    ARTIFACT_TYPE,
    STRATEGY_SECTIONS,
    build_strategy,
)
from tests.fixtures.numbers import FULL_TABLE
from tests.fixtures.steps import (
    FakeLLM,
    FakeRetriever,
    make_strategy_corpus,
    valid_strategy_section_json,
)
from tests.fixtures.xbrl_facts import make_facts

REVENUE_TAG = "RevenueFromContractWithCustomerExcludingAssessedTax"
OPERATING_INCOME_TAG = "OperatingIncomeLoss"
NET_INCOME_TAG = "NetIncomeLoss"
EQUITY_TAG = "StockholdersEquity"
TOTAL_ASSETS_TAG = "Assets"
CURRENT_LIABILITIES_TAG = "LiabilitiesCurrent"
LONG_TERM_DEBT_TAG = "LongTermDebt"
LONG_TERM_DEBT_CURRENT_TAG = "LongTermDebtCurrent"
CASH_TAG = "CashAndCashEquivalentsAtCarryingValue"
BEFORE_TAX_TAG = "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"
TAX_TAG = "IncomeTaxExpenseBenefit"


def strategy_financials():
    return compute(make_facts(FULL_TABLE))


def make_generator(corpus=None, llm=None):
    retriever = FakeRetriever(corpus) if corpus is not None else FakeRetriever(make_strategy_corpus())
    return ArtifactGenerator(
        retriever,
        llm or FakeLLM(valid_strategy_section_json()),
    )


class TestStrategySections:
    def test_strategy_drafts_plan_capex_and_financing_in_order(self):
        generator = make_generator()
        artifact = generator.generate("TSLA", ARTIFACT_TYPE, STRATEGY_SECTIONS)
        keys = [s.key for s in artifact.sections]
        assert keys == ["plan", "capex", "financing"]
        for section in artifact.sections:
            assert section.content
            assert len(section.sources) >= 1
            assert section.evidence
        assert artifact.scope.items == ["ITEM 5", "ITEM 7"]

    def test_strategy_specs_scope_to_item_5_and_7(self):
        items = set()
        for spec in STRATEGY_SECTIONS:
            items.update(spec.items)
        assert items == {"ITEM 5", "ITEM 7"}


class TestBuildStrategy:
    def test_build_strategy_combines_sections_and_returns_table(self):
        artifact = build_strategy(make_generator(), "TSLA", strategy_financials())
        assert artifact.artifact_type == ARTIFACT_TYPE
        assert artifact.ticker == "TSLA"
        assert artifact.fiscal_year == 2025
        assert [s.key for s in artifact.sections] == ["plan", "capex", "financing"]
        returns = artifact.returns
        assert returns is not None
        assert returns.key == "returns"
        assert returns.title == "Long-run returns"
        assert returns.unit == "percent"
        assert returns.columns[0] == "2025"

    def test_build_strategy_returns_table_lists_roic_roe_roce(self):
        artifact = build_strategy(make_generator(), "TSLA", strategy_financials())
        labels = {r.label for r in artifact.returns.rows}
        assert labels == {"ROIC", "ROE", "ROCE"}

    def test_build_strategy_returns_rows_carry_xbrl_fact_citations(self):
        artifact = build_strategy(make_generator(), "TSLA", strategy_financials())
        rows = {r.label: r for r in artifact.returns.rows}
        roe_facts = {t.value for t in rows["ROE"].sources}
        assert NET_INCOME_TAG in roe_facts
        assert EQUITY_TAG in roe_facts
        roce_facts = {t.value for t in rows["ROCE"].sources}
        assert OPERATING_INCOME_TAG in roce_facts
        assert TOTAL_ASSETS_TAG in roce_facts
        assert CURRENT_LIABILITIES_TAG in roce_facts
        roic_facts = {t.value for t in rows["ROIC"].sources}
        assert OPERATING_INCOME_TAG in roic_facts
        assert LONG_TERM_DEBT_TAG in roic_facts
        assert LONG_TERM_DEBT_CURRENT_TAG in roic_facts
        assert EQUITY_TAG in roic_facts
        assert CASH_TAG in roic_facts
        assert BEFORE_TAX_TAG in roic_facts
        assert TAX_TAG in roic_facts

    def test_build_strategy_returns_matches_worked_examples(self):
        artifact = build_strategy(make_generator(), "TSLA", strategy_financials())
        rows = {r.label: r for r in artifact.returns.rows}
        assert rows["ROE"].values["2025"] == pytest.approx(0.12)
        assert rows["ROCE"].values["2025"] == pytest.approx(22.5 / 250.0)

    def test_build_strategy_checks_plan_against_long_run_returns(self):
        llm = FakeLLM(valid_strategy_section_json())
        artifact = build_strategy(make_generator(llm=llm), "TSLA", strategy_financials())
        assert [s.key for s in artifact.sections] == ["plan", "capex", "financing"]
        plan_prompt = llm.prompts[0]
        assert "long-run returns from the numbers layer" in plan_prompt
        assert "ROIC" in plan_prompt
        assert "consistent with this track record" in plan_prompt

    def test_build_strategy_drops_returns_table_when_ratios_missing(self):
        sparse = compute(
            make_facts(
                {"RevenueFromContractWithCustomerExcludingAssessedTax": {y: 100 for y in range(2020, 2026)}}
            )
        )
        artifact = build_strategy(make_generator(), "TSLA", sparse)
        assert artifact.returns is None
