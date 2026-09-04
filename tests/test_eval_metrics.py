"""Unit tests for the pure retrieval-ranking metrics (``metrics.py``).

These are the shared scoring primitives behind every T13 eval mode
(curated benchmark, synthetic regression, and the dashboard's per-step
numbers), kept free of LlamaIndex and the network so they are trivially
unit-testable.
"""

import math

import pytest

from financial_analyst.evaluation.metrics import (
    aggregate,
    hit_rate_at_k,
    mean,
    mrr_at_k,
    ndcg_at_k,
    query_metrics,
)


class TestMrrAtK:
    def test_zero_when_nothing_relevant(self):
        assert mrr_at_k([False, False, False, False]) == 0.0

    def test_one_over_rank_of_first_relevant(self):
        assert mrr_at_k([False, True, False, False]) == 0.5
        assert mrr_at_k([True, False, False, False]) == 1.0
        assert mrr_at_k([False, False, True, False]) == pytest.approx(1 / 3)

    def test_empty_returns_zero(self):
        assert mrr_at_k([]) == 0.0


class TestHitRateAtK:
    def test_one_when_any_relevant(self):
        assert hit_rate_at_k([True, False, False]) == 1.0
        assert hit_rate_at_k([False, False, True]) == 1.0

    def test_zero_when_none_relevant(self):
        assert hit_rate_at_k([False, False]) == 0.0
        assert hit_rate_at_k([]) == 0.0


class TestNdcgAtK:
    def test_ignores_positions_beyond_retrieved(self):
        assert ndcg_at_k([True, False, False, False], 4, expected_positives=1) == 1.0

    def test_relevant_at_one_and_three_with_two_expected(self):
        # DCG = 1/log2(2) + 1/log2(4) = 1 + 0.5 = 1.5
        # IDCG = 1/log2(2) + 1/log2(3) ~= 1.6309
        got = ndcg_at_k([True, False, True, False], 4, expected_positives=2)
        assert got == pytest.approx(1.5 / (1 + 1 / math.log2(3)))

    def test_none_when_nothing_expected(self):
        assert ndcg_at_k([False, False], 4, expected_positives=0) is None

    def test_zero_when_nothing_retrieved_but_expected(self):
        assert ndcg_at_k([False, False, False], 4, expected_positives=2) == 0.0

    def test_expected_positives_cap_at_k_for_idcg(self):
        # Two relevant docs at the only two retrieved positions.
        got = ndcg_at_k([True, True], 2, expected_positives=5)
        assert got == pytest.approx(1.0)


class TestQueryMetrics:
    def test_full_row(self):
        row = query_metrics([True, False, True], k=4, expected_positives=2)
        assert row["mrr"] == 1.0
        assert row["hit_rate"] == 1.0
        assert row["ndcg"] is not None

    def test_missing_ndcg_when_no_positives_expected(self):
        row = query_metrics([], k=4, expected_positives=0)
        assert row == {"mrr": 0.0, "hit_rate": 0.0, "ndcg": None}


class TestMeanAndAggregate:
    def test_mean_drops_none(self):
        assert mean([0.5, None, 0.7]) == pytest.approx(0.6)
        assert mean([None, None]) is None
        assert mean([]) is None

    def test_aggregate_averages_present_ndcg(self):
        rows = [
            {"mrr": 1.0, "hit_rate": 1.0, "ndcg": 1.0},
            {"mrr": 0.5, "hit_rate": 1.0, "ndcg": None},
            {"mrr": 0.0, "hit_rate": 0.0, "ndcg": 0.0},
        ]
        out = aggregate(rows)
        assert out["num_queries"] == 3
        assert out["mrr"] == pytest.approx(0.5)
        assert out["hit_rate"] == pytest.approx(2 / 3)
        assert out["ndcg"] == pytest.approx(0.5)

    def test_aggregate_empty(self):
        out = aggregate([])
        assert out == {"num_queries": 0, "mrr": None, "hit_rate": None, "ndcg": None}
