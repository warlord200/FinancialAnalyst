"""Unit tests for the eval report store and continuity checks.

``report.py`` persists the eval results the dashboard serves
(``storage/evals/dashboard.json``) and holds the regression *continuity*
logic: whether a synthetic-set run has drifted below its recorded baseline
past a tolerance. The dashboard merge and the baseline comparison are pure
file/dict logic, so they get the same offline treatment as the metrics.
"""

import json
from pathlib import Path

import pytest

from financial_analyst.evaluation.report import (
    DEFAULT_SECTIONS,
    attach_continuity,
    compare_continuity,
    load_baselines,
    load_dashboard,
    update_dashboard,
)

BASELINE = {
    "top_k": 4,
    "datasets": {
        "2026_Tesla": {
            "hybrid": {"mrr": 0.851, "hit_rate": 0.951, "ndcg": 0.877},
        }
    },
}


def write_baselines(tmp_path, data=None):
    path = tmp_path / "regression_baselines.json"
    path.write_text(json.dumps(data or BASELINE), encoding="utf-8")
    return path


class TestDashboardStore:
    def test_update_writes_a_section(self, tmp_path):
        path = tmp_path / "dashboard.json"
        update_dashboard(path, "curated", [{"name": "t"}])
        assert path.exists()
        doc = load_dashboard(path)
        assert doc["curated"] == [{"name": "t"}]
        assert "generated_at" in doc

    def test_update_replaces_whole_section(self, tmp_path):
        path = tmp_path / "dashboard.json"
        update_dashboard(path, "curated", [{"name": "t"}])
        update_dashboard(path, "curated", [{"name": "u"}])
        assert load_dashboard(path)["curated"] == [{"name": "u"}]

    def test_update_keeps_other_sections(self, tmp_path):
        path = tmp_path / "dashboard.json"
        update_dashboard(path, "curated", [{"name": "t"}])
        update_dashboard(path, "smoke", [{"ticker": "TSLA"}])
        doc = load_dashboard(path)
        assert doc["curated"] == [{"name": "t"}]
        assert doc["smoke"] == [{"ticker": "TSLA"}]

    def test_load_missing_file_returns_none(self, tmp_path):
        assert load_dashboard(tmp_path / "nope.json") is None

    def test_unknown_sections_are_initialised(self, tmp_path):
        path = tmp_path / "dashboard.json"
        update_dashboard(path, "curated", [{"a": 1}])
        doc = load_dashboard(path)
        assert set(doc) == {"generated_at", *DEFAULT_SECTIONS}
        assert doc["regression"] == []
        assert doc["smoke"] == []


class TestContinuity:
    def test_regression_flagged_when_metric_drops_past_tolerance(self):
        measured = {"mrr": 0.820, "hit_rate": 0.951, "ndcg": 0.877}
        out = compare_continuity(measured, BASELINE["datasets"]["2026_Tesla"]["hybrid"], tolerance=0.02)
        assert out["regressed"] is True
        assert "mrr" in out["regressions"]
        assert out["deltas"]["mrr"] == pytest.approx(-0.031)

    def test_drop_within_tolerance_is_not_a_regression(self):
        measured = {"mrr": 0.842, "hit_rate": 0.951, "ndcg": 0.877}
        out = compare_continuity(measured, BASELINE["datasets"]["2026_Tesla"]["hybrid"], tolerance=0.02)
        assert out["regressed"] is False
        assert out["regressions"] == []

    def test_improvements_are_not_regressions(self):
        measured = {"mrr": 0.88, "hit_rate": 0.96, "ndcg": 0.9}
        out = compare_continuity(measured, BASELINE["datasets"]["2026_Tesla"]["hybrid"], tolerance=0.02)
        assert out["regressed"] is False
        assert all(delta >= 0 for delta in out["deltas"].values())

    def test_metrics_missing_from_baseline_are_skipped(self):
        # The measured row only reports mrr; the baseline has no mrr, so
        # nothing is comparable and nothing can regress.
        measured = {"mrr": 0.8}
        out = compare_continuity(
            measured,
            {"hit_rate": 0.951, "ndcg": 0.877},
            tolerance=0.02,
        )
        assert out["regressed"] is False
        assert out["regressions"] == []

    def test_attach_continuity_builds_a_dashboard_row(self):
        measured = {"num_queries": 163, "mrr": 0.82, "hit_rate": 0.95, "ndcg": 0.87}
        row = attach_continuity(
            measured,
            BASELINE["datasets"]["2026_Tesla"]["hybrid"],
            tolerance=0.02,
            dataset="2026_Tesla",
            config="hybrid",
        )
        assert row["dataset"] == "2026_Tesla"
        assert row["config"] == "hybrid"
        assert row["baseline_mrr"] == pytest.approx(0.851)
        assert row["regressed"] is True


class TestBaselines:
    def test_load_baselines_reads_json(self, tmp_path):
        data = load_baselines(write_baselines(tmp_path))
        assert data["datasets"]["2026_Tesla"]["hybrid"]["mrr"] == pytest.approx(0.851)

    def test_load_baselines_default_path_missing_is_empty(self, tmp_path):
        data = load_baselines(tmp_path / "missing.json")
        assert data == {"top_k": None, "datasets": {}}
