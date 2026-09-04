"""Unit tests for the curated-benchmark data model and relevance matching.

The curated Tesla benchmark stores hand-written analyst questions whose
ground truth is a set of *chunk references*: each reference names the
chunk's Item and fiscal year (when the scope is unambiguous) plus a
verbatim snippet that a retrieval hit must contain. These tests pin the
model (``benchmarks.py``) and the matching rules shared by the runner.
"""

import json
from pathlib import Path

import pytest

from financial_analyst.evaluation.benchmarks import (
    CURATED_BENCHMARK_PATH,
    CuratedBenchmark,
    CuratedQuestion,
    RelevantChunk,
    SUPPORTED_STEPS,
    load_curated_benchmark,
    matching_entries,
    normalize,
    save_curated_benchmark,
    step_key,
)

TSLA_CHUNKS = [
    {
        "text": "Tesla designs, develops, manufactures and sells electric vehicles.",
        "item": "ITEM 1",
        "fiscal_year": 2025,
    },
    {
        "text": "Demand for our vehicles depends on charging infrastructure.",
        "item": "ITEM 1A",
        "fiscal_year": 2025,
    },
    {
        "text": "Automotive revenues grew 55% in fiscal 2025.",
        "item": "ITEM 7",
        "fiscal_year": 2025,
    },
]


class Chunk:
    def __init__(self, text, item=None, fiscal_year=None):
        self.text = text
        self.item = item
        self.fiscal_year = fiscal_year


class TestNormalize:
    def test_collapses_whitespace_and_case(self):
        assert normalize("  Tesla\nDesigns   EV  ") == "tesla designs ev"

    def test_empty(self):
        assert normalize("") == ""
        assert normalize("   ") == ""

    def test_flattens_quote_and_dash_variants(self):
        assert normalize("\u201cAI\u201d\u2014based") == "ai based"
        assert normalize("Don\u2019t stop") == "dont stop"
        assert normalize("high-performance") == "high performance"
        assert normalize("real\u2013time") == "real time"


class TestRelevantChunkMatch:
    def test_text_snippet_matches_when_contained(self):
        entry = RelevantChunk(text="designs, develops, manufactures")
        chunk = Chunk(TSLA_CHUNKS[0]["text"], "ITEM 1", 2025)
        assert matching_entries(chunk, [entry]) == [0]

    def test_item_and_year_are_filters_when_present(self):
        entry = RelevantChunk(
            text="designs, develops, manufactures", item="ITEM 1", fiscal_year=2025
        )
        assert matching_entries(Chunk(TSLA_CHUNKS[0]["text"], "ITEM 1", 2025), [entry]) == [0]
        # Same text on a different Item is not a match.
        assert matching_entries(Chunk(TSLA_CHUNKS[0]["text"], "ITEM 7", 2025), [entry]) == []
        # Same text in a different fiscal year is not a match.
        assert matching_entries(Chunk(TSLA_CHUNKS[0]["text"], "ITEM 1", 2024), [entry]) == []

    def test_missing_chunk_metadata_never_matches_a_constrained_entry(self):
        entry = RelevantChunk(
            text="designs, develops, manufactures", item="ITEM 1", fiscal_year=2025
        )
        assert matching_entries(Chunk(TSLA_CHUNKS[0]["text"]), [entry]) == []
        assert matching_entries(Chunk(TSLA_CHUNKS[0]["text"], "ITEM 1"), [entry]) == []

    def test_unconstrained_entry_matches_by_text_alone(self):
        entry = RelevantChunk(text="automotive revenues grew 55%")
        assert matching_entries(Chunk(TSLA_CHUNKS[2]["text"], "ITEM 7", 2025), [entry]) == [0]
        # Case/whitespace differences between the snippet and the corpus chunk
        # are tolerated by normalization.
        loose = RelevantChunk(text="  automotive  REVENUES\ngrew")
        assert matching_entries(Chunk(TSLA_CHUNKS[2]["text"], "ITEM 7", 2025), [loose]) == [0]

    def test_returns_index_of_every_matching_entry(self):
        entries = [
            RelevantChunk(text="designs, develops"),
            RelevantChunk(text="sells electric vehicles"),
            RelevantChunk(text="charging infrastructure"),
        ]
        chunk = Chunk(TSLA_CHUNKS[0]["text"], "ITEM 1", 2025)
        assert matching_entries(chunk, entries) == [0, 1]


class TestStepKey:
    def test_scoped_steps_keep_their_number(self):
        assert step_key(2) == "2"
        assert step_key(4) == "4"

    def test_unscoped_queries_are_search_all(self):
        assert step_key(None) == "search_all"


class TestCuratedBenchmarkRoundTrip:
    def make_benchmark(self):
        return CuratedBenchmark(
            name="tesla-analyst-2026",
            ticker="TSLA",
            description="Hand-curated analyst questions",
            top_k=4,
            questions=[
                CuratedQuestion(
                    id="q01",
                    step=3,
                    question="How did automotive revenue move?",
                    relevant=[
                        RelevantChunk(
                            text="Automotive revenues grew 55%",
                            item="ITEM 7",
                            fiscal_year=2025,
                        )
                    ],
                ),
                CuratedQuestion(
                    id="q02",
                    step=None,
                    question="Search everything",
                    relevant=[RelevantChunk(text="demand for our vehicles")],
                ),
            ],
        )

    def test_round_trips_through_json(self, tmp_path):
        bm = self.make_benchmark()
        path = tmp_path / "tesla.json"
        save_curated_benchmark(bm, path)
        loaded = load_curated_benchmark(path)
        assert loaded == bm

    def test_load_rejects_missing_questions_file(self, tmp_path):
        with pytest.raises(Exception):
            load_curated_benchmark(tmp_path / "nope.json")

    def test_query_counts_by_step(self):
        bm = self.make_benchmark()
        counts = bm.query_counts_by_step()
        assert counts == {"3": 1, "search_all": 1}

    def test_questions_load_with_expected_shape(self, tmp_path):
        raw = {
            "name": "x",
            "ticker": "TSLA",
            "questions": [
                {"id": "a", "step": 2, "question": "q", "relevant": [{"text": "t"}]}
            ],
        }
        path = tmp_path / "x.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        loaded = load_curated_benchmark(path)
        assert loaded.questions[0].relevant[0].item is None
        assert Path(path).exists()


class TestShippedTeslaBenchmark:
    def test_asset_is_well_formed(self):
        assert CURATED_BENCHMARK_PATH.is_file()
        bm = load_curated_benchmark(CURATED_BENCHMARK_PATH)
        assert bm.ticker == "TSLA"
        assert len(bm.questions) >= 10
        ids = [q.id for q in bm.questions]
        assert len(ids) == len(set(ids))
        for q in bm.questions:
            assert q.question
            assert q.step is None or q.step in SUPPORTED_STEPS
            assert q.relevant, f"{q.id} has no ground truth"
            assert all(r.text.strip() for r in q.relevant)
        counts = bm.query_counts_by_step()
        assert all(counts.get(str(s), 0) >= 2 for s in SUPPORTED_STEPS)
        assert counts.get("search_all", 0) >= 1
