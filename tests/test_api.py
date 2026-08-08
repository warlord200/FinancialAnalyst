from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from api.main import create_app


def make_client():
    app = create_app()
    return TestClient(app)


def test_health_ok():
    resp = make_client().get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_analyze_and_get_report(monkeypatch):
    fake = MagicMock()
    fake.analyze.return_value = {"status": "completed", "report_path": "storage/TSLA/report.md"}
    fake.get_report.return_value = {
        "ticker": "TSLA",
        "fiscal_years": [2025, 2024],
        "generated_at": "2026-08-07T00:00:00",
        "verdict": {"label": "bullish", "score": 72, "rationale": "Growth."},
        "markdown": "# Executive Summary\n\nbody",
    }

    import api.main as main

    monkeypatch.setattr(main, "_get_analyzer", lambda: fake)
    client = TestClient(create_app())

    resp = client.post("/api/analyze/tsla")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    fake.analyze.assert_called_once_with("TSLA")

    resp = client.get("/api/report/TSLA")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "TSLA"
    assert body["verdict"]["score"] == 72
    assert body["markdown"].startswith("# Executive Summary")


def test_get_report_404_when_missing(monkeypatch):
    import api.main as main

    monkeypatch.setattr(main, "_get_analyzer", lambda: MagicMock(get_report=MagicMock(return_value=None)))
    resp = make_client().get("/api/report/NOPE")
    assert resp.status_code == 404


def test_tickers_and_reanalyze(monkeypatch):
    fake = MagicMock()
    fake.list_tickers.return_value = [{"ticker": "TSLA"}]
    fake.reanalyze.return_value = {"status": "completed", "report_path": "x"}

    import api.main as main

    monkeypatch.setattr(main, "_get_analyzer", lambda: fake)
    client = TestClient(create_app())

    assert client.get("/api/tickers").json() == [{"ticker": "TSLA"}]
    resp = client.post("/api/reanalyze/TSLA")
    assert resp.status_code == 200
    fake.reanalyze.assert_called_once_with("TSLA")
