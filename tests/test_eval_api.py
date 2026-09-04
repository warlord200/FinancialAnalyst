"""API tests for the eval summary endpoint.

``GET /api/eval/summary`` serves the dashboard snapshot the eval CLI writes
(``storage/evals/dashboard.json``) to the web dashboard. It is auth-gated
like every other endpoint and 404s when no eval has run yet.
"""

import pytest
from fastapi.testclient import TestClient

import api.main as main
from tests.auth_helpers import GENEROUS_LIMITS, build_client, signup_and_auth


def make_client(tmp_path, monkeypatch, summary):
    monkeypatch.setattr(main, "_load_eval_summary", lambda: summary)
    client, _, _ = build_client(tmp_path, monkeypatch, limits=GENEROUS_LIMITS)
    return client


SUMMARY = {
    "generated_at": "2026-09-05T00:00:00+00:00",
    "curated": [
        {
            "name": "tesla-analyst-2026",
            "ticker": "TSLA",
            "top_k": 4,
            "config": "hybrid",
            "per_step": {
                "2": {"num_queries": 4, "mrr": 0.8, "hit_rate": 1.0, "ndcg": 0.9},
                "3": {"num_queries": 4, "mrr": 0.5, "hit_rate": 0.75, "ndcg": 0.6},
            },
        }
    ],
    "regression": [],
    "smoke": [],
}


def test_requires_authentication(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch, SUMMARY)
    resp = client.get("/api/eval/summary")
    assert resp.status_code == 401


def test_returns_dashboard_payload_when_present(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch, SUMMARY)
    signup_and_auth(client, email="eval@example.com")
    resp = client.get("/api/eval/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["generated_at"]
    assert body["curated"][0]["ticker"] == "TSLA"
    assert body["curated"][0]["per_step"]["2"]["mrr"] == 0.8
    assert body["regression"] == []


def test_404_when_no_eval_has_run(tmp_path, monkeypatch):
    client = make_client(tmp_path, monkeypatch, None)
    signup_and_auth(client, email="eval@example.com")
    resp = client.get("/api/eval/summary")
    assert resp.status_code == 404
