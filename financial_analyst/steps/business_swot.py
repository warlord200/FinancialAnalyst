"""Step 2: the Business and SWOT artifact.

A source-tagged draft covering what the company does, how it earns money,
its customers, suppliers, regulators, and management, generated from
Item 1 / Item 1A of the latest 10-K, and organized into a SWOT.
"""

from financial_analyst.steps.generation import SectionSpec

BUSINESS_SWOT_SECTIONS = (
    SectionSpec(
        key="overview",
        heading="Business Overview",
        query=(
            "What does the company do? Describe its core business, its main products "
            "and services, and its overall strategy."
        ),
        instruction="Cover what the company makes or does and the markets it serves.",
    ),
    SectionSpec(
        key="segments",
        heading="Segments",
        query=(
            "What are the company's operating and reportable segments? Describe each "
            "segment and what it does."
        ),
        instruction=(
            "Name segments explicitly when the filing does; otherwise say the company "
            "does not report segment detail."
        ),
    ),
    SectionSpec(
        key="revenue_model",
        heading="Revenue Model",
        query=(
            "How does the company earn money? Describe its revenue streams and whether "
            "revenue is recurring or one-off."
        ),
        instruction="Be explicit about recurring versus one-off revenue.",
    ),
    SectionSpec(
        key="customers",
        heading="Customers",
        query=(
            "Who are the company's customers? Describe customer segments, concentration, "
            "and dependence on any customer."
        ),
        instruction="Mention customer concentration only if the filing does.",
    ),
    SectionSpec(
        key="suppliers",
        heading="Suppliers",
        query=(
            "Who are the company's suppliers? Describe key inputs, sourcing, and "
            "supply-chain dependencies."
        ),
        instruction="Mention supply chain risk only if the filing does.",
    ),
    SectionSpec(
        key="regulators",
        heading="Regulators",
        query=(
            "What regulators and regulations affect the company? Describe the regulatory "
            "environment the business operates in."
        ),
        instruction="Name the specific agencies or regulations the filing mentions.",
    ),
    SectionSpec(
        key="management",
        heading="Management",
        query=(
            "What does the filing say about the company's management and leadership?"
        ),
        instruction=(
            "Cover only what the filing actually states; do not invent names or biographies."
        ),
    ),
    SectionSpec(
        key="swot_strengths",
        heading="Strengths",
        query="What strengths of the company does the filing describe?",
        instruction="List strengths as short bullets, each grounded in a source passage.",
        context_from=("overview", "segments", "revenue_model", "customers"),
    ),
    SectionSpec(
        key="swot_weaknesses",
        heading="Weaknesses",
        query="What weaknesses of the company does the filing describe?",
        instruction="List weaknesses as short bullets, each grounded in a source passage.",
        context_from=("overview", "segments", "revenue_model", "suppliers"),
    ),
    SectionSpec(
        key="swot_opportunities",
        heading="Opportunities",
        query="What opportunities for the company does the filing describe?",
        instruction=(
            "List opportunities as short bullets, each grounded in a source passage."
        ),
        context_from=("overview", "segments", "revenue_model", "regulators"),
    ),
    SectionSpec(
        key="swot_threats",
        heading="Threats",
        query="What threats to the company does the filing describe?",
        instruction="List threats as short bullets, each grounded in a source passage.",
        context_from=("overview", "suppliers", "regulators"),
    ),
)

ARTIFACT_TYPE = "business_swot"


def build_business_swot(generator, ticker: str):
    return generator.generate(ticker, ARTIFACT_TYPE, BUSINESS_SWOT_SECTIONS)
