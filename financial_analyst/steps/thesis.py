"""Step 6: the Thesis.

The final artifact of the dossier. The thesis document is a read-only,
source-tagged summary of the investment case — what the investor would
hold, why, the key assumptions it rests on, and what would change their
mind — plus a devil's advocate section arguing the opposite side and a
list of open research gaps. It is drafted over the corpus so the devil's
advocate and gaps are grounded by construction in source passages. The
document is not editable: it is the grounded draft presented under the
canonical headings below, and it is cached per ticker so repeat views are
instant and stable.

The draft has six sections, each grounded like the other drafted
artifacts (steps 2-4): every section cites the source passages it drew
on, with verbatim evidence. The devil's advocate query and instruction
are written to argue *against* the position, so the grounded negative
case is where an investor can stress-test the thesis.
"""

from financial_analyst.steps.generation import Artifact, SectionSpec

THESIS_TYPE = "thesis"

# The thesis synthesises the whole dossier, so the draft draws on every
# filing section the earlier steps already read.
THESIS_ITEMS = ("ITEM 1", "ITEM 1A", "ITEM 5", "ITEM 7", "ITEM 8")

THESIS_SECTIONS = (
    SectionSpec(
        key="hold",
        heading="What I hold",
        query=(
            "Weigh the business quality, financial health, strategy, and risks described "
            "in the filing. What position does the evidence best support an investor taking, "
            "and with what conviction?"
        ),
        instruction=(
            "Propose the position the evidence supports (for example own the stock, avoid it, "
            "or stay on the sidelines) and say how strongly the evidence points that way. "
            "Ground every reason in the source passages."
        ),
        items=THESIS_ITEMS,
        top_k=6,
    ),
    SectionSpec(
        key="why",
        heading="Why I hold it",
        query=(
            "What are the strongest reasons to own this company, based on the business, "
            "financials, and strategy the filing describes?"
        ),
        instruction=(
            "State the strongest reasons for the position, each tied to a source passage. "
            "Distinguish durable advantages from one-off effects."
        ),
        items=THESIS_ITEMS,
        top_k=6,
    ),
    SectionSpec(
        key="assumptions",
        heading="Key assumptions",
        query=(
            "What assumptions does the investment case rest on — growth, margins, capital "
            "needs, competitive position, or balance-sheet policy — and what does the filing "
            "say about each?"
        ),
        instruction=(
            "List the assumptions the position depends on. For each, cite the passage that "
            "supports it or flag the assumption the filing cannot verify."
        ),
        items=THESIS_ITEMS,
        top_k=6,
    ),
    SectionSpec(
        key="triggers",
        heading="What would change my mind",
        query=(
            "Which risks, trends, or events described in the filing would weaken or invalidate "
            "the investment case?"
        ),
        instruction=(
            "Name the concrete developments that would change the position — deterioration in "
            "the business, balance-sheet strain, competitive or regulatory threats — and cite "
            "the passage that flags each."
        ),
        items=THESIS_ITEMS,
        top_k=6,
    ),
    SectionSpec(
        key="devils_advocate",
        heading="Devil's advocate",
        query=(
            "What is the strongest case against taking this position? Collect the negative "
            "evidence the filing presents: risks, weaknesses, and cautious language."
        ),
        instruction=(
            "Argue against the position as forcefully as the filing's own evidence allows. "
            "Every point of the counter-case must cite a source passage; do not soften it."
        ),
        items=THESIS_ITEMS,
        top_k=6,
    ),
    SectionSpec(
        key="gaps",
        heading="Open research gaps",
        query=(
            "What important questions about the company does the filing leave open or answer "
            "only partially?"
        ),
        instruction=(
            "List the questions the filing does not resolve, and for each say what additional "
            "information would answer it. Cite the passage that raised the question or that "
            "shows the information is absent."
        ),
        items=THESIS_ITEMS,
        top_k=6,
    ),
)


def thesis_section_keys() -> list[str]:
    """The thesis document's section keys, in canonical order."""
    return [spec.key for spec in THESIS_SECTIONS]


def build_thesis(generator, ticker: str) -> Artifact:
    """Draft the six grounded thesis sections over the dossier corpus.

    The returned artifact *is* the thesis: the read-only document shown to
    the user is its content under the canonical headings, with the source
    tags and evidence it was grounded on attached to each section.
    """
    return generator.generate(ticker, THESIS_TYPE, THESIS_SECTIONS)
