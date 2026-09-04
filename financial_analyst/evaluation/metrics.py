"""Pure retrieval-ranking metrics shared by every T13 eval mode.

The curated benchmark, the synthetic regression sets, and the per-company
smoke evals all reduce to the same question: given a ranked list of
retrieved results, where the ground truth says *how many* results matter,
how good is the ranking? These functions answer it at a cut-off ``k`` with
binary per-position relevance and need no framework types, so the math is
unit-testable in isolation.

``mrr_at_k`` and ``hit_rate_at_k`` depend only on the ranked relevance
gains. ``ndcg_at_k`` additionally needs ``expected_positives`` (how many
relevant chunks the query's ground truth declares) to compute the ideal
DCG; a query with no expected positives has no meaningful NDCG and scores
``None``, which aggregation drops rather than treating as a zero.
"""

import math
from typing import Sequence

METRICS = ["mrr", "hit_rate", "ndcg"]


def mrr_at_k(gains: Sequence[bool]) -> float:
    """Reciprocal rank of the first relevant result (0 when none)."""
    for rank, gain in enumerate(gains, start=1):
        if gain:
            return 1.0 / rank
    return 0.0


def hit_rate_at_k(gains: Sequence[bool]) -> float:
    """Whether any result in the ranked list is relevant."""
    return 1.0 if any(gains) else 0.0


def ndcg_at_k(
    gains: Sequence[bool],
    k: int,
    expected_positives: int,
) -> float | None:
    """Normalized discounted cumulative gain at cut-off ``k``.

    Binary gains: each relevant result at 1-based rank ``i`` contributes
    ``1 / log2(i + 1)``. The ideal DCG assumes the best possible ordering
    of the ``expected_positives`` relevant chunks, capped at ``k`` retrieved
    slots. Returns ``None`` when there is nothing positive to retrieve, so
    the query cannot be meaningfully scored.
    """
    if expected_positives <= 0 or k <= 0:
        return None
    dcg = sum(1.0 / math.log2(i + 1) for i, g in enumerate(gains[:k], start=1) if g)
    ideal = min(expected_positives, k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal + 1))
    if idcg <= 0:
        return None
    return dcg / idcg


def query_metrics(
    gains: list[bool],
    k: int,
    expected_positives: int,
) -> dict[str, float | None]:
    """The three metrics for one query as a flat dict."""
    return {
        "mrr": mrr_at_k(gains),
        "hit_rate": hit_rate_at_k(gains),
        "ndcg": ndcg_at_k(gains, k, expected_positives),
    }


def mean(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present) / len(present)


def aggregate(rows: Sequence[dict]) -> dict[str, float | None | int]:
    """Mean each metric over per-query result rows.

    Rows are dicts with ``mrr``/``hit_rate``/``ndcg`` keys (values may be
    ``None``); the mean is taken over the queries where the metric is
    defined, mirroring how the manual harness reports aggregate NDCG.
    """
    if not rows:
        return {"num_queries": 0, "mrr": None, "hit_rate": None, "ndcg": None}
    return {
        "num_queries": len(rows),
        "mrr": mean([r["mrr"] for r in rows]),
        "hit_rate": mean([r["hit_rate"] for r in rows]),
        "ndcg": mean([r["ndcg"] for r in rows]),
    }
