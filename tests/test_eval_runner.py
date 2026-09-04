"""Unit tests for the curated-benchmark runner (``runner.py``).

``run_curated_benchmark`` is the per-step scoped scoring engine: it asks a
``retrieve`` callable for each benchmark question's top chunks and scores
the ranking against the question's multi-chunk ground truth. It never
touches an index or embedder itself — the caller supplies retrieval — so
these tests drive it with scripted results and pin the per-step
aggregation and the dashboard payload shape.
"""

import math

import pytest

from financial_analyst.evaluation.benchmarks import (
    CuratedBenchmark,
    CuratedQuestion,
    RelevantChunk,
)
from financial_analyst.evaluation.runner import (
    InvalidStepError,
    run_curated_benchmark,
    scoped_retrieve,
)
from financial_analyst.steps.retrieval import SourceChunk

Q2 = "2"
Q3 = "3"
ALL = "search_all"


def chunk(text, item="ITEM 7", fiscal_year=2025):
    return SourceChunk(text=text, item=item, fiscal_year=fiscal_year, ticker="TSLA")


def benchmark(*questions):
    return CuratedBenchmark(name="t", ticker="TSLA", top_k=4, questions=list(questions))


def q(question_id, step, relevant_texts, item="ITEM 7", fiscal_year=2025):
    return CuratedQuestion(
        id=question_id,
        step=step,
        question=f"{question_id}?",
        relevant=[
            RelevantChunk(text=t, item=item, fiscal_year=fiscal_year) for t in relevant_texts
        ],
    )


class TestRunCuratedBenchmark:
    def test_per_query_metrics_from_retrieved_rank(self):
        bm = benchmark(
            q("a", 3, ["revenue grew"], item="ITEM 7"),
            q("b", 3, ["energy business"], item="ITEM 7"),
        )

        def retrieve(question):
            if question.id == "a":
                # Relevant chunk is second.
                return [chunk("irrelevant filler"), chunk("Revenue grew 10% in 2025.")]
            return [chunk("no match anywhere.")]

        out = run_curated_benchmark(bm, retrieve)
        rows = {r["question_id"]: r for r in out["per_query"]}
        assert rows["a"]["mrr"] == pytest.approx(0.5)
        assert rows["a"]["hit_rate"] == 1.0
        assert rows["b"]["mrr"] == 0.0
        assert rows["b"]["hit_rate"] == 0.0

    def test_multi_chunk_ground_truth_and_ndcg(self):
        # Two expected chunks, both recovered: ranks 1 and 3.
        bm = benchmark(
            q(
                "m",
                3,
                ["revenue grew", "energy business"],
                item="ITEM 7",
            )
        )

        def retrieve(question):
            return [
                chunk("Revenue grew strongly in fiscal 2025."),
                chunk("unrelated filler"),
                chunk("The energy business expanded."),
            ]

        out = run_curated_benchmark(bm, retrieve)
        row = out["per_query"][0]
        assert row["matched"] == 2
        assert row["all_expected_found"] is True
        # DCG = 1 + 1/log2(4) = 1.5; IDCG = 1 + 1/log2(3).
        assert row["ndcg"] == pytest.approx(1.5 / (1 + 1 / math.log2(3)))
        assert row["mrr"] == 1.0

    def test_one_chunk_covering_two_references_recovers_one_chunk(self):
        # Two references live in the same retrieved chunk; a single hit can
        # only recover one chunk, so NDCG caps against the two expected.
        bm = benchmark(q("m", 2, ["designs EVs", "sells EVs"], item="ITEM 1"))

        def retrieve(question):
            return [chunk("Tesla designs EVs and sells EVs.", item="ITEM 1")]

        out = run_curated_benchmark(bm, retrieve)
        row = out["per_query"][0]
        assert row["matched"] == 1
        assert row["all_expected_found"] is False
        assert row["ndcg"] == pytest.approx(1 / (1 + 1 / math.log2(3)))

    def test_step_filter_constraints_are_enforced(self):
        # The relevant snippet is an ITEM 7 claim; retrieved ITEM 1 chunks
        # cannot satisfy it even when the wording matches.
        bm = benchmark(
            q("c", 3, ["revenue grew"]),
        )

        def retrieve(question):
            return [chunk("Revenue grew but this is Item 1.", item="ITEM 1")]

        out = run_curated_benchmark(bm, retrieve)
        assert out["per_query"][0]["hit_rate"] == 0.0

    def test_per_step_aggregation_buckets_queries(self):
        bm = benchmark(
            q("s2a", 2, ["designs EVs"], item="ITEM 1"),
            q("s2b", 2, ["competition"], item="ITEM 1A"),
            q("s3a", 3, ["revenue"], item="ITEM 7"),
            q("sall", None, ["revenue"], item="ITEM 7"),
        )

        def retrieve(question):
            return [chunk("designs EVs competition revenue", item="ITEM 1")]

        out = run_curated_benchmark(bm, retrieve)
        per_step = out["per_step"]
        assert set(per_step) == {Q2, Q3, "4", ALL}
        assert per_step[Q2]["num_queries"] == 2
        assert per_step[Q3]["num_queries"] == 1
        assert per_step[ALL]["num_queries"] == 1
        assert per_step["4"]["num_queries"] == 0

    def test_trims_retrieved_results_to_top_k(self):
        bm = benchmark(q("a", 3, ["want this"]))
        calls = {"n": 0}

        def retrieve(question):
            calls["n"] += 1
            return [
                chunk(f"filler {i}", item="ITEM 7") for i in range(10)
            ] + [chunk("want this at position 11", item="ITEM 7")]

        out = run_curated_benchmark(bm, retrieve)
        row = out["per_query"][0]
        assert row["retrieved"] == 4
        assert row["hit_rate"] == 0.0

    def test_invalid_step_rejected(self):
        bm = benchmark(q("bad", 5, ["x"]))
        with pytest.raises(InvalidStepError):
            run_curated_benchmark(bm, lambda question: [])

    def test_payload_metadata(self):
        bm = benchmark(q("a", 3, ["revenue grew"]))

        out = run_curated_benchmark(bm, lambda question: [])
        assert out["name"] == "t"
        assert out["ticker"] == "TSLA"
        assert out["top_k"] == 4
        assert "run_at" in out


class FakeRetriever:
    def __init__(self, results_by_query):
        self.results_by_query = results_by_query
        self.calls = []

    def retrieve(self, ticker, query, items=None, fiscal_year=None, top_k=None):
        self.calls.append((query, items))
        return self.results_by_query.get(query, [])


class TestScopedRetrieve:
    def test_maps_step_to_its_source_items(self):
        fake = FakeRetriever(
            {
                "id?": [chunk("Energy business", item="ITEM 7")],
            }
        )
        question = q("id", 3, ["energy"], item="ITEM 7")
        got = scoped_retrieve(fake, "TSLA", question, top_k=6)
        assert fake.calls == [("id?", ["ITEM 7", "ITEM 8"])]
        assert len(got) == 1

    def test_unscoped_question_searches_everything(self):
        fake = FakeRetriever({"q": [chunk("anything")]})
        question = q("id", None, ["energy"])
        scoped_retrieve(fake, "TSLA", question)
        assert fake.calls == [("id?", None)]
