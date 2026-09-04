"""Curated retrieval benchmark data model.

The curated benchmark is the retrieval quality gate's hand-labelled set: a
real company (``ticker``), a list of real analyst questions, and, per
question, the chunks a correct answer needs. Because a re-ingest
regenerates chunk ids, ground truth is stored as *chunk references* rather
than corpus ids: each reference names the chunk's Item and fiscal year
when the scope is unambiguous, plus a verbatim snippet of the chunk that a
retrieval hit must contain. The runner resolves references against live
retrieval results by matching (see ``matching_entries``), so the benchmark
survives chunk-boundary changes as long as the prose survives.

A question's ``step`` says which dossier scope the retriever was run under
(2 = Item 1/1A, 3 = Item 7/8, 4 = Item 5/7 per ``STEP_SCOPES``); ``None``
means the whole corpus was searched (the search-everything escape hatch).
Per-step metrics aggregate the questions that share a scope.
"""

import json
from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, Field

SUPPORTED_STEPS = (2, 3, 4)

# The tracked hand-curated set shipped with the package (used by the CLI
# ``curated`` subcommand and by the eval dashboard).
BENCHMARKS_DIR = Path(__file__).parent / "benchmarks"
CURATED_BENCHMARK_PATH = BENCHMARKS_DIR / "tesla_analyst_2026.json"


def normalize(text: str) -> str:
    """Collapse whitespace and case for snippet-to-chunk comparisons.

    Punctuation variants a re-ingest or an OCR pass might change — curly
    quotes/apostrophes, straight quotes, and dashes — are flattened too
    (quotes are dropped, dashes become spaces), so a hand-written snippet
    still matches the corpus it was written from without depending on the
    exact glyphs in the filing text.
    """
    text = str(text)
    text = text.replace("\u2018", "").replace("\u2019", "")
    text = text.replace("\u201c", "").replace("\u201d", "")
    text = text.replace("'", "").replace('"', "")
    for dash in ("\u2013", "\u2014", "\u2026", "-", "\u2212"):
        text = text.replace(dash, " ")
    return " ".join(text.split()).lower()


def step_key(step: int | None) -> str:
    """The dashboard's bucket for a question's scope."""
    return "search_all" if step is None else str(step)


class RelevantChunk(BaseModel):
    text: str
    item: str | None = None
    fiscal_year: int | None = None


class CuratedQuestion(BaseModel):
    id: str
    question: str
    step: int | None = None
    relevant: list[RelevantChunk] = Field(default_factory=list)


class CuratedBenchmark(BaseModel):
    name: str
    ticker: str
    description: str = ""
    top_k: int = 4
    questions: list[CuratedQuestion] = Field(default_factory=list)

    def query_counts_by_step(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for question in self.questions:
            key = step_key(question.step)
            counts[key] = counts.get(key, 0) + 1
        return counts


def load_curated_benchmark(path: str | Path) -> CuratedBenchmark:
    with open(path, encoding="utf-8") as f:
        return CuratedBenchmark(**json.load(f))


def save_curated_benchmark(benchmark: CuratedBenchmark, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(benchmark.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def entry_matches_chunk(entry: RelevantChunk, chunk) -> bool:
    """Whether one ground-truth reference is satisfied by a retrieved chunk.

    ``chunk`` is duck-typed: anything with ``text``/``item``/``fiscal_year``
    (``SourceChunk`` or the eval's ``CorpusChunk``) works. A reference with
    an Item or fiscal year constraint only matches a chunk that carries the
    same metadata, so an Item 7 snippet cannot be satisfied by an Item 1
    hit even when the prose overlaps; a snippet with no constraints matches
    purely on content.
    """
    if entry.item is not None:
        if not chunk.item or entry.item.lower() != str(chunk.item).lower():
            return False
    if entry.fiscal_year is not None:
        if chunk.fiscal_year is None or entry.fiscal_year != chunk.fiscal_year:
            return False
    if not entry.text:
        return False
    return normalize(entry.text) in normalize(chunk.text)


def matching_entries(chunk, entries: Sequence[RelevantChunk]) -> list[int]:
    """Indexes of every ground-truth reference a chunk satisfies.

    The runner uses this to give each retrieved position its relevance
    gain, deduplicating references across earlier positions so one chunk is
    never counted as two of a query's expected positives.
    """
    return [i for i, entry in enumerate(entries) if entry_matches_chunk(entry, chunk)]
