"""Running the curated benchmark with per-step scoped scoring.

``run_curated_benchmark`` is deliberately decoupled from the index and the
embedder: it takes a ``retrieve`` callable and scores what comes back
against the benchmark's multi-chunk ground truth. Per-step metrics fall out
of bucketing each question by the dossier scope it was asked under
(``benchmarks.step_key``). The production CLI wires ``retrieve`` to the
live ``ScopedRetriever`` through :func:`scoped_retrieve`, which applies the
same Item scopes the step chat service does — step 2 reads Item 1/1A,
step 3 reads Item 7/8, step 4 reads Item 5/7, and an unscoped question
searches the whole corpus.
"""

from datetime import datetime, timezone
from typing import Callable, Sequence

from financial_analyst.evaluation.benchmarks import (
    SUPPORTED_STEPS,
    CuratedBenchmark,
    CuratedQuestion,
    matching_entries,
    step_key,
)
from financial_analyst.evaluation.metrics import METRICS, aggregate, query_metrics
from financial_analyst.steps import STEP_SCOPES
from financial_analyst.steps.retrieval import SourceChunk


class InvalidStepError(Exception):
    def __init__(self, step: int) -> None:
        super().__init__(
            f"Benchmark question has unsupported step {step!r}; "
            f"supported steps are {SUPPORTED_STEPS} or None (search everything)."
        )
        self.step = step


RetrieveCallable = Callable[[CuratedQuestion], Sequence[SourceChunk]]


def scoped_retrieve(
    retriever,
    ticker: str,
    question: CuratedQuestion,
    top_k: int | None = None,
) -> list[SourceChunk]:
    """Retrieve a benchmark question under its dossier step's Item scope."""
    items = None if question.step is None else list(STEP_SCOPES[question.step])
    return retriever.retrieve(
        ticker,
        question.question,
        items=items,
        top_k=top_k,
    )


def _score_question(
    question: CuratedQuestion,
    chunks: Sequence[SourceChunk],
    top_k: int,
) -> dict:
    trimmed = list(chunks[:top_k])
    seen: set[int] = set()
    gains: list[bool] = []
    for chunk in trimmed:
        new = [i for i in matching_entries(chunk, question.relevant) if i not in seen]
        if new:
            seen.update(new)
        gains.append(bool(new))
    metrics = query_metrics(gains, k=top_k, expected_positives=len(question.relevant))
    return {
        "question_id": question.id,
        "step": question.step,
        "expected_positives": len(question.relevant),
        "retrieved": len(trimmed),
        "matched": sum(1 for g in gains if g),
        "all_expected_found": sum(1 for g in gains if g) == len(question.relevant),
        **metrics,
    }


def run_curated_benchmark(
    benchmark: CuratedBenchmark,
    retrieve: RetrieveCallable,
) -> dict:
    """Score every question and aggregate per dossier step.

    Returns the dashboard payload for one curated run: per-query rows plus
    aggregate metrics keyed by ``step_key`` (``"2"``, ``"3"``, ``"4"``, and
    ``"search_all"``). A question with an unsupported step raises
    :class:`InvalidStepError` so a malformed benchmark is caught loudly.
    """
    for question in benchmark.questions:
        if question.step is not None and question.step not in SUPPORTED_STEPS:
            raise InvalidStepError(question.step)

    rows: list[dict] = []
    for question in benchmark.questions:
        chunks = retrieve(question)
        rows.append(_score_question(question, chunks, benchmark.top_k))

    buckets: dict[str, list[dict]] = {str(s): [] for s in SUPPORTED_STEPS}
    buckets["search_all"] = []
    for row in rows:
        buckets[step_key(row["step"])].append(row)

    per_step = {
        key: aggregate(rows_in_bucket)
        for key, rows_in_bucket in buckets.items()
    }
    return {
        "name": benchmark.name,
        "ticker": benchmark.ticker,
        "top_k": benchmark.top_k,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "metrics": METRICS,
        "per_query": rows,
        "per_step": per_step,
    }
