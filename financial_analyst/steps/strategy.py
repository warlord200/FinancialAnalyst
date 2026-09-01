"""Step 4: the Strategy artifact.

A hybrid step like Step 3: the drafted plan, capex, and financing sections
come from the generation framework over Item 5 / Item 7 (the market-for-
shares and MD&A sections), and the long-run returns check (ROIC / ROE /
ROCE) comes straight from the numbers layer, so it is grounded by
construction and carries ``xbrl_fact`` source tags pointing at the exact
us-gaap concepts it is derived from.

The plan section is drafted with the long-run returns track record in its
instruction, so the draft actually checks the stated plan against the
numbers rather than just displaying the two side by side.
"""

import dataclasses

from financial_analyst.steps.financials import RATIO_LABELS, FinancialTable, build_tables
from financial_analyst.steps.generation import Artifact, SectionSpec

ARTIFACT_TYPE = "strategy"

RETURNS_NAMES = ("roic", "roe", "roce")

STRATEGY_SECTIONS = (
    SectionSpec(
        key="plan",
        heading="Management's Plan",
        query=(
            "What is management's stated plan for the company? Describe its strategy, "
            "growth initiatives, and outlook."
        ),
        instruction=(
            "Cover only what the filing states. Distinguish stated plans and intentions "
            "from what the company has already done, and cite the passage you relied on."
        ),
        items=("ITEM 5", "ITEM 7"),
    ),
    SectionSpec(
        key="capex",
        heading="Capital Expenditures",
        query=(
            "What does the filing say about capital expenditures? Describe planned or "
            "actual spending on property, plant, and equipment."
        ),
        instruction=(
            "Cover only what the filing states about capital expenditures and any stated "
            "investment plans. If the filing does not discuss capex, say so explicitly and "
            "cite the passage you relied on for that judgment."
        ),
        items=("ITEM 5", "ITEM 7"),
    ),
    SectionSpec(
        key="financing",
        heading="Financing",
        query=(
            "How does the company finance itself: with debt or by issuing shares? "
            "Describe the financing approach the filing describes."
        ),
        instruction=(
            "Cover only what the filing states about how the company raises capital — "
            "debt versus equity, dividends, and buybacks. Name the instrument explicitly "
            "when the filing does."
        ),
        items=("ITEM 5", "ITEM 7"),
    ),
)


class StrategyArtifact(Artifact):
    returns: FinancialTable | None = None


def build_returns(financials: dict) -> FinancialTable | None:
    """Pick the long-run returns table (ROIC / ROE / ROCE) from the numbers
    layer. It is built by the shared financials table builder, so it carries
    the same XBRL-fact source tags on every row."""
    for table in build_tables(financials):
        if table.key == "returns":
            return table.model_copy(update={"title": "Long-run returns"})
    return None


def _returns_context(financials: dict) -> str:
    """A one-line summary of the long-run returns track record, threaded into
    the plan section's instruction so the draft checks the plan against it."""
    ratios = financials.get("ratios", {})
    years = [str(year) for year in financials.get("fiscal_years", [])]
    parts = []
    for name in RETURNS_NAMES:
        values = ratios.get(name, {})
        series = [values[y] for y in years if values.get(y) is not None]
        if not series:
            continue
        latest = series[-1]
        avg = sum(series) / len(series)
        parts.append(f"{RATIO_LABELS[name]} {latest:.1%} latest, {avg:.1%} {len(series)}y avg")
    return "; ".join(parts)


def _plan_sections(financials: dict) -> tuple[SectionSpec, ...]:
    context = _returns_context(financials)
    if not context:
        return STRATEGY_SECTIONS
    plan = STRATEGY_SECTIONS[0]
    checked = dataclasses.replace(
        plan,
        instruction=(
            f"{plan.instruction} The long-run returns from the numbers layer are: "
            f"{context}. Judge whether the stated plan is consistent with this track "
            "record, and say so explicitly."
        ),
    )
    return (checked,) + STRATEGY_SECTIONS[1:]


def build_strategy(generator, ticker: str, financials: dict) -> StrategyArtifact:
    """Draft the plan, capex, and financing sections through the generation
    framework and combine them with the long-run returns table from the
    numbers layer into the strategy artifact."""
    drafted = generator.generate(ticker, ARTIFACT_TYPE, _plan_sections(financials))
    return StrategyArtifact(
        ticker=drafted.ticker,
        artifact_type=ARTIFACT_TYPE,
        fiscal_year=drafted.fiscal_year,
        scope=drafted.scope,
        generated_at=drafted.generated_at,
        sections=drafted.sections,
        returns=build_returns(financials),
    )
