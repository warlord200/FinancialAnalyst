import pytest

import api.main as main
from financial_analyst.numbers.prices import PriceStore
from financial_analyst.numbers.service import NumbersService, NumbersStore
from financial_analyst.steps.service import StepsService
from financial_analyst.steps.state import StepStateStore
from tests.auth_helpers import GENEROUS_LIMITS, build_client, signup_and_auth
from tests.fixtures.numbers import (
    FULL_TABLE,
    FakeDownloader,
    FakeFactsFetcher,
    FakePriceClient,
)
from tests.fixtures.xbrl_facts import make_facts


def make_steps_client(tmp_path, monkeypatch, ciks=None, facts=None, price_client=None):
    numbers = NumbersService(
        downloader=FakeDownloader(ciks or {"TSLA": 1318605}),
        facts_fetcher=FakeFactsFetcher(facts or make_facts(FULL_TABLE)),
        price_client=price_client or FakePriceClient(),
        store=NumbersStore(str(tmp_path / "storage" / "numbers.json")),
        price_store=PriceStore(str(tmp_path / "storage" / "prices.json")),
    )
    steps = StepsService(
        numbers_service=numbers,
        state_store=StepStateStore(str(tmp_path / "storage" / "steps.db")),
    )
    monkeypatch.setattr(main, "_get_numbers_service", lambda: numbers)
    monkeypatch.setattr(main, "_get_steps_service", lambda: steps)
    client, _, _ = build_client(tmp_path, monkeypatch, limits=GENEROUS_LIMITS)
    signup_and_auth(client, email="steps@example.com")
    return client, steps, numbers


def refresh(client, ticker="TSLA"):
    assert client.post(f"/api/numbers/{ticker}/refresh").status_code == 200


class TestOnePager:
    def test_one_pager_renders_from_numbers_layer(self, tmp_path, monkeypatch):
        client, _, _ = make_steps_client(tmp_path, monkeypatch)
        refresh(client)
        resp = client.get("/api/steps/TSLA/one-pager")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ticker"] == "TSLA"
        assert body["gate"] is None
        one = body["one_pager"]
        assert one["latest_fiscal_year"] == 2025
        assert one["source"] == "SEC XBRL company-facts (us-gaap)"
        assert one["growth"]["latest_revenue"] == 150.0
        assert one["growth"]["revenue_growth_yoy"] == pytest.approx((150 - 140) / 140)
        assert one["growth"]["revenue_cagr_5y"] == pytest.approx(1.5 ** 0.2 - 1)
        assert one["profitability"]["gross_margin"] == pytest.approx(0.25)
        assert one["profitability"]["operating_margin"] == pytest.approx(0.15)
        assert one["profitability"]["net_margin"] == pytest.approx(0.10)
        assert one["debt"]["debt_to_assets"] == pytest.approx(60 / 350)
        assert one["debt"]["debt_to_equity"] == pytest.approx(60 / 125)

    def test_one_pager_tag_is_rule_based_and_deterministic(self, tmp_path, monkeypatch):
        client, _, _ = make_steps_client(tmp_path, monkeypatch)
        refresh(client)
        tag = client.get("/api/steps/TSLA/one-pager").json()["one_pager"]["tag"]
        assert tag["label"] == "neutral"
        assert tag["score"] == 67
        assert "8.4%" in tag["rationale"]
        assert "10.0%" in tag["rationale"]
        assert "17.1%" in tag["rationale"]

    def test_one_pager_404_when_numbers_missing(self, tmp_path, monkeypatch):
        client, _, _ = make_steps_client(tmp_path, monkeypatch)
        assert client.get("/api/steps/TSLA/one-pager").status_code == 404

    def test_one_pager_requires_auth(self, tmp_path, monkeypatch):
        client, _, _ = build_client(tmp_path, monkeypatch)
        assert client.get("/api/steps/TSLA/one-pager").status_code == 401

    def test_one_pager_renders_for_any_ingested_ticker(self, tmp_path, monkeypatch):
        client, _, _ = make_steps_client(tmp_path, monkeypatch, ciks={"TSLA": 1, "AAPL": 2})
        refresh(client, "TSLA")
        refresh(client, "AAPL")
        resp = client.get("/api/steps/AAPL/one-pager")
        assert resp.status_code == 200
        assert resp.json()["one_pager"]["growth"]["latest_revenue"] == 150.0


class TestGate:
    def test_accept_gate_persists(self, tmp_path, monkeypatch):
        client, _, _ = make_steps_client(tmp_path, monkeypatch)
        refresh(client)
        resp = client.post("/api/steps/TSLA/gate", json={"decision": "accept"})
        assert resp.status_code == 200
        gate = resp.json()["gate"]
        assert gate["step"] == 1
        assert gate["status"] == "accepted"
        body = client.get("/api/steps/TSLA/one-pager").json()
        assert body["gate"]["status"] == "accepted"

    def test_reject_gate_persists(self, tmp_path, monkeypatch):
        client, _, _ = make_steps_client(tmp_path, monkeypatch)
        refresh(client)
        resp = client.post("/api/steps/TSLA/gate", json={"decision": "reject"})
        assert resp.status_code == 200
        assert resp.json()["gate"]["status"] == "rejected"
        assert client.get("/api/steps/TSLA/one-pager").json()["gate"]["status"] == "rejected"

    def test_gate_can_be_reopened(self, tmp_path, monkeypatch):
        client, _, _ = make_steps_client(tmp_path, monkeypatch)
        refresh(client)
        client.post("/api/steps/TSLA/gate", json={"decision": "reject"})
        resp = client.post("/api/steps/TSLA/gate", json={"decision": "accept"})
        assert resp.json()["gate"]["status"] == "accepted"

    def test_gate_is_per_user(self, tmp_path, monkeypatch):
        client, _, _ = make_steps_client(tmp_path, monkeypatch)
        refresh(client)
        client.post("/api/steps/TSLA/gate", json={"decision": "accept"})

        bob_client, _, _ = build_client(tmp_path, monkeypatch, limits=GENEROUS_LIMITS)
        signup_and_auth(bob_client, email="bob@example.com")
        assert bob_client.get("/api/steps/TSLA/one-pager").json()["gate"] is None

    def test_gate_404_when_numbers_missing(self, tmp_path, monkeypatch):
        client, _, _ = make_steps_client(tmp_path, monkeypatch)
        resp = client.post("/api/steps/TSLA/gate", json={"decision": "accept"})
        assert resp.status_code == 404

    def test_gate_rejects_invalid_decision(self, tmp_path, monkeypatch):
        client, _, _ = make_steps_client(tmp_path, monkeypatch)
        refresh(client)
        resp = client.post("/api/steps/TSLA/gate", json={"decision": "maybe"})
        assert resp.status_code == 422
