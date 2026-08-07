import json
from pathlib import Path

from financial_analyst.storage.registry import CacheRegistry


def sample_entry():
    return {
        "fiscal_years": [2025, 2024],
        "report_path": "storage/TSLA/report.md",
        "report_generated_at": "2026-08-07T10:00:00",
        "verdict": {"label": "bullish", "score": 72, "rationale": "Strong revenue growth."},
    }


def test_add_and_get(tmp_path):
    reg = CacheRegistry(str(tmp_path / "registry.json"))
    reg.add("tsla", sample_entry())

    entry = reg.get("TSLA")
    assert entry is not None
    assert entry["verdict"]["score"] == 72
    assert entry["fiscal_years"] == [2025, 2024]


def test_persistence_round_trip(tmp_path):
    path = tmp_path / "registry.json"
    reg1 = CacheRegistry(str(path))
    reg1.add("TSLA", sample_entry())

    reg2 = CacheRegistry(str(path))
    entry = reg2.get("TSLA")
    assert entry == sample_entry()


def test_clear(tmp_path):
    reg = CacheRegistry(str(tmp_path / "registry.json"))
    reg.add("TSLA", sample_entry())
    reg.clear("TSLA")
    assert reg.get("TSLA") is None


def test_list_all_sorted_by_recency(tmp_path):
    reg = CacheRegistry(str(tmp_path / "registry.json"))
    old = {**sample_entry(), "report_generated_at": "2026-01-01T00:00:00"}
    new = {**sample_entry(), "report_generated_at": "2026-08-07T00:00:00"}
    reg.add("OLD", old)
    reg.add("NEW", new)

    entries = reg.list_all()
    assert [e["ticker"] for e in entries] == ["NEW", "OLD"]
