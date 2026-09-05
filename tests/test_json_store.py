import json

from financial_analyst.storage.json_store import JsonFileStore


def _dump(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_reader_reloads_external_write(tmp_path):
    path = tmp_path / "store.json"
    store = JsonFileStore(str(path))
    assert store.all() == {}

    _dump(path, {"TSLA": {"ingested_at": "2026-09-05T10:00:00"}})

    assert store.get("TSLA")["ingested_at"] == "2026-09-05T10:00:00"
    assert set(store.all()) == {"TSLA"}


def test_reader_reloads_external_removal(tmp_path):
    path = tmp_path / "store.json"
    store = JsonFileStore(str(path))
    _dump(path, {"TSLA": {"ingested_at": "2026-09-05T10:00:00"}})
    assert store.get("TSLA") is not None

    _dump(path, {})
    assert store.get("TSLA") is None
    assert store.all() == {}


def test_read_sees_latest_value_after_overwrite(tmp_path):
    path = tmp_path / "store.json"
    store = JsonFileStore(str(path))
    _dump(path, {"TSLA": {"ingested_at": "2026-09-05T10:00:00"}})
    _dump(path, {"TSLA": {"ingested_at": "2026-09-05T11:00:00"}})

    assert store.get("TSLA")["ingested_at"] == "2026-09-05T11:00:00"


def test_set_does_not_clobber_external_keys(tmp_path):
    path = tmp_path / "store.json"
    store = JsonFileStore(str(path))
    _dump(path, {"TSLA": {"ingested_at": "2026-09-05T10:00:00"}})

    store.set("AAPL", {"ingested_at": "2026-09-05T12:00:00"})

    assert set(store.all()) == {"TSLA", "AAPL"}
