"""Unit tests for the per-company smoke eval (``smoke.py``).

``run_smoke`` is the automated gate for a freshly ingested company that has
no hand-curated benchmark yet. For every dossier chat step (2, 3, 4) it
checks the corpus covers the step's Items, samples chunks from that scope,
and confirms retrieval finds each source chunk again when asked with its
own opening words — a structural check that each scope is retrievable under
the production Item filters. These tests drive the retrieval seam with
scripted retrievers.
"""

from financial_analyst.evaluation.corpus import CorpusChunk
from financial_analyst.evaluation.smoke import STEP_SCOPES, _query_from_chunk, run_smoke
from financial_analyst.steps.retrieval import SourceChunk

CHUNKS = [
    CorpusChunk("c1", "Tesla designs and manufactures electric vehicles.", "ITEM 1"),
    CorpusChunk("c2", "Our business faces competition from other automakers.", "ITEM 1A"),
    CorpusChunk("c3", "Revenue and gross profit grew strongly in fiscal 2025.", "ITEM 7"),
    CorpusChunk("c4", "The financial statements are presented in the notes.", "ITEM 8"),
    CorpusChunk("c5", "We repurchase shares under a board-authorised plan.", "ITEM 5"),
    CorpusChunk("c6", "Liquidity and capital resources discussion for the year.", "ITEM 7"),
]


def as_source(chunk):
    return SourceChunk(
        text=chunk.text, item=chunk.item, fiscal_year=chunk.fiscal_year, ticker="TSLA"
    )


def make_prefix_retriever(chunks):
    """Returns the source chunk whose text the query is a prefix of."""
    calls = []

    def retrieve(query, items):
        calls.append((query, tuple(items)))
        for chunk in chunks:
            if chunk.item in items and chunk.text.startswith(query):
                return [as_source(chunk)]
        return []

    return retrieve, calls


class TestQueryFromChunk:
    def test_uses_the_opening_words_of_the_chunk(self):
        text = (
            "Tesla designs and manufactures electric vehicles across our "
            "factories and sells them to consumers worldwide."
        )
        query = _query_from_chunk(text)
        assert query.startswith("Tesla designs and manufactures")
        assert len(query.split()) <= 40

    def test_short_chunk_is_kept_whole(self):
        assert _query_from_chunk("Short chunk here.") == "Short chunk here."


class TestRunSmoke:
    def test_passes_when_every_scope_is_covered_and_retrievable(self):
        retrieve, _ = make_prefix_retriever(CHUNKS)
        out = run_smoke("TSLA", CHUNKS, retrieve, samples_per_step=2)
        assert out["ticker"] == "TSLA"
        assert out["passed"] is True
        for step_out in out["steps"].values():
            assert step_out["skipped"] is False
            assert step_out["samples"] == 2
            assert step_out["retrieval_hit_rate"] == 1.0
            assert step_out["in_scope_rate"] == 1.0

    def test_checks_list_which_scope_items_are_missing(self):
        chunks = [c for c in CHUNKS if c.item in ("ITEM 1", "ITEM 1A")]
        retrieve, _ = make_prefix_retriever(chunks)
        out = run_smoke("TSLA", chunks, retrieve, samples_per_step=1)
        assert out["passed"] is False
        assert out["checks"]["3"]["items_missing"] == ["ITEM 7", "ITEM 8"]
        assert out["steps"]["3"]["skipped"] is True

    def test_fails_when_retrieval_cannot_find_the_source_chunk(self):
        def retrieve(query, items):
            return []

        out = run_smoke("TSLA", CHUNKS, retrieve, samples_per_step=2)
        assert out["passed"] is False
        assert out["steps"]["3"]["retrieval_hit_rate"] == 0.0

    def test_out_of_scope_hits_lower_in_scope_rate(self):
        def retrieve(query, items):
            return [as_source(CorpusChunk("x", "unrelated text", "ITEM 1"))]

        out = run_smoke("TSLA", CHUNKS, retrieve, samples_per_step=2)
        assert out["passed"] is False
        assert out["steps"]["3"]["in_scope_rate"] == 0.0
        # Step 2 samples land only on ITEM 1 chunks, and the generic result
        # carries ITEM 1 metadata, so step 2 keeps its in-scope rate.
        assert out["steps"]["2"]["in_scope_rate"] == 1.0

    def test_hit_floor_is_configurable(self):
        def miss_step3(query, items):
            if "ITEM 7" in items and "ITEM 8" in items:
                return []
            return []

        lenient = run_smoke("TSLA", CHUNKS, miss_step3, samples_per_step=2, hit_floor=0.0)
        assert lenient["steps"]["3"]["retrieval_hit_rate"] == 0.0
        assert lenient["passed"] is True
        strict = run_smoke("TSLA", CHUNKS, miss_step3, samples_per_step=2, hit_floor=1.0)
        assert strict["passed"] is False

    def test_deterministic_given_seed(self):
        retrieve, _ = make_prefix_retriever(CHUNKS)
        a = run_smoke("TSLA", CHUNKS, retrieve, samples_per_step=2, seed=7)
        b = run_smoke("TSLA", CHUNKS, retrieve, samples_per_step=2, seed=7)
        assert a["steps"] == b["steps"]
        assert a["checks"] == b["checks"]

    def test_retrieval_asked_with_the_steps_item_scope(self):
        retrieve, calls = make_prefix_retriever(CHUNKS)
        run_smoke("TSLA", CHUNKS, retrieve, samples_per_step=1)
        scopes = {items for _, items in calls}
        assert tuple(STEP_SCOPES[2]) in scopes
        assert tuple(STEP_SCOPES[3]) in scopes
        assert tuple(STEP_SCOPES[4]) in scopes

    def test_returns_an_error_for_an_empty_corpus(self):
        retrieve, _ = make_prefix_retriever([])
        out = run_smoke("TSLA", [], retrieve)
        assert out["passed"] is False
