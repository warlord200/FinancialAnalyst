"""The automated per-company smoke eval.

A freshly ingested company has no hand-curated benchmark, so it gets a
structural gate instead. ``run_smoke`` walks every dossier chat step that
draws on the corpus (steps 2-4) and checks two things per step:

- **coverage**: the company's corpus actually contains chunks for each Item
  in the step's scope (step 2 -> Item 1/1A, step 3 -> Item 7/8, step 4 ->
  Item 5/7 per ``STEP_SCOPES``), and
- **retrievability**: a seeded sample of that scope's chunks is still found
  when the retriever is asked for the chunk's own opening words under the
  step's Item filter — catching an empty scope, an embed-model mismatch, or
  a broken hybrid/rerank path for a company the corpus was just built for.

``retrieve`` is the seam the CLI wires to the live ``ScopedRetriever``; the
run reports per-step retrieval-hit and in-scope rates plus a pass/fail
flag driven by a configurable ``hit_floor``. A smoke failure is advisory —
it never fails the ingest job itself, only records the problem.
"""

import random
from datetime import datetime, timezone

from financial_analyst.steps import STEP_SCOPES

_QUERY_MAX_TOKENS = 40


def _query_from_chunk(text: str, max_tokens: int = _QUERY_MAX_TOKENS) -> str:
    """The opening words of a chunk, used as its self-retrieval query."""
    words = " ".join(text.split()).split()
    return " ".join(words[:max_tokens])


def _same_chunk(result, source) -> bool:
    """Whether a retrieved chunk is the sampled source chunk (by content
    and scope metadata; chunk ids are not stable across re-ingests)."""
    return (
        result.item == source.item
        and result.fiscal_year == source.fiscal_year
        and " ".join(result.text.split()) == " ".join(source.text.split())
    )


def run_smoke(
    ticker: str,
    chunks: list,
    retrieve,
    *,
    samples_per_step: int = 3,
    top_k: int = 4,
    seed: int = 0,
    hit_floor: float = 1.0,
) -> dict:
    """Run the coverage + self-retrieval gate over every chat step scope.

    ``retrieve(query, items)`` returns the ranked chunks for ``query``
    filtered to ``items`` (a list of Item labels, or None for the whole
    corpus). The returned dict is the dashboard's ``smoke`` section entry.
    """
    rng = random.Random(seed)
    checks: dict[str, dict] = {}
    steps: dict[str, dict] = {}
    passed = True

    for step in sorted(STEP_SCOPES):
        items = list(STEP_SCOPES[step])
        scope_chunks = [c for c in chunks if c.item in items]
        present = sorted({c.item for c in scope_chunks})
        missing = [item for item in items if item not in present]
        checks[str(step)] = {
            "items": items,
            "items_present": present,
            "items_missing": missing,
        }
        step_out: dict = {
            "samples": 0,
            "skipped": False,
            "retrieval_hit_rate": None,
            "in_scope_rate": None,
        }
        if missing or not scope_chunks:
            step_out["skipped"] = True
            steps[str(step)] = step_out
            passed = False
            continue

        chosen = rng.sample(scope_chunks, min(samples_per_step, len(scope_chunks)))
        hits = 0
        returned_total = 0
        in_scope_total = 0
        for source in chosen:
            returned = list(retrieve(_query_from_chunk(source.text), items))[:top_k]
            returned_total += len(returned)
            hits += int(any(_same_chunk(result, source) for result in returned))
            in_scope_total += sum(1 for result in returned if result.item in items)

        step_out["samples"] = len(chosen)
        step_out["retrieval_hit_rate"] = round(hits / len(chosen), 4)
        if returned_total:
            step_out["in_scope_rate"] = round(in_scope_total / returned_total, 4)
        if step_out["retrieval_hit_rate"] < hit_floor:
            passed = False
        if step_out["in_scope_rate"] is not None and step_out["in_scope_rate"] < 1.0:
            passed = False
        steps[str(step)] = step_out

    if not chunks:
        passed = False

    return {
        "ticker": ticker.upper(),
        "run_at": datetime.now(timezone.utc).isoformat(),
        "samples_per_step": samples_per_step,
        "seed": seed,
        "checks": checks,
        "steps": steps,
        "passed": passed,
    }
