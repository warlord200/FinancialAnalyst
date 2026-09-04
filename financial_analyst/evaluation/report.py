"""Eval run persistence and the regression continuity gate.

The eval harness writes one dashboard snapshot that the API serves and the
web dashboard renders: ``storage/evals/dashboard.json``, a single JSON
object whose three lists (``curated``, ``regression``, ``smoke``) hold the
latest run of each eval mode. ``update_dashboard`` merges one mode's
results in without disturbing the others, so an operator can re-run a
single mode and the dashboard reflects only that change.

The synthetic regression sets carry recorded baselines (the measured
numbers in README "METRICS" for the current embed model), shipped as a
tracked asset under ``financial_analyst/evaluation/baselines``. Continuity
is a drift gate: a run is a *regression* when any measured metric has
fallen more than ``tolerance`` (absolute) below its baseline. It is a
report, not a hard failure: the CLI prints and stores the regressions so
an operator decides whether to re-ingest or investigate.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from financial_analyst.evaluation.metrics import METRICS

DEFAULT_SECTIONS = ["curated", "regression", "smoke"]

DEFAULT_DASHBOARD_PATH = "storage/evals/dashboard.json"

_BASELINES_DIR = Path(__file__).parent / "baselines"
DEFAULT_BASELINES_PATH = _BASELINES_DIR / "regression.json"

# Hard-coded tolerance and rounding shared by every regression row.
DEFAULT_REGRESSION_TOLERANCE = 0.02


def load_dashboard(path: str | Path = DEFAULT_DASHBOARD_PATH) -> dict | None:
    path = Path(path)
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def update_dashboard(
    path: str | Path,
    section: str,
    entries: list[dict],
) -> None:
    """Replace one section of the dashboard snapshot with ``entries``."""
    path = Path(path)
    doc = load_dashboard(path)
    if doc is None:
        doc = {"generated_at": None, **{s: [] for s in DEFAULT_SECTIONS}}
    doc[section] = entries
    doc["generated_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_baselines(path: str | Path = DEFAULT_BASELINES_PATH) -> dict:
    path = Path(path)
    if not path.is_file():
        return {"top_k": None, "datasets": {}}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {
        "top_k": data.get("top_k"),
        "datasets": data.get("datasets", {}),
    }


def compare_continuity(
    measured: dict[str, float],
    baseline: dict[str, float],
    tolerance: float = DEFAULT_REGRESSION_TOLERANCE,
) -> dict:
    """Drift of one config's measured metrics against its baseline.

    Returns ``regressed`` (any metric below its baseline by more than
    ``tolerance``), the names of the regressed metrics, and every metric's
    measured-minus-baseline delta. Metrics absent from the baseline are
    skipped rather than treated as a regression.
    """
    deltas: dict[str, float] = {}
    regressions: list[str] = []
    for metric in METRICS:
        if metric not in baseline or metric not in measured:
            continue
        if baseline[metric] is None or measured[metric] is None:
            continue
        delta = float(measured[metric]) - float(baseline[metric])
        deltas[metric] = round(delta, 4)
        if delta < -tolerance:
            regressions.append(metric)
    return {
        "regressed": bool(regressions),
        "regressions": regressions,
        "deltas": deltas,
    }


def attach_continuity(
    measured: dict[str, Any],
    baseline: dict[str, float] | None,
    *,
    dataset: str,
    config: str,
    tolerance: float = DEFAULT_REGRESSION_TOLERANCE,
) -> dict:
    """One dashboard regression row: measured metrics plus baseline context."""
    baseline = baseline or {}
    continuity = compare_continuity(measured, baseline, tolerance)
    row: dict[str, Any] = {
        "dataset": dataset,
        "config": config,
        "num_queries": measured.get("num_queries", 0),
        "regressed": continuity["regressed"],
        "regressions": continuity["regressions"],
    }
    for metric in METRICS:
        row[metric] = _round(measured.get(metric))
        row[f"baseline_{metric}"] = _round(baseline.get(metric))
        row[f"delta_{metric}"] = continuity["deltas"].get(metric)
    return row
