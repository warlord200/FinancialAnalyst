"""HTTP API tests for the Step 5 valuation (T11).

The app under test is the real FastAPI app with a faked service boundary:
numbers come from a NumbersService backed by per-CIK facts and a price
client returning a fixed $25 price with a five-year history, and per-user
done-marks and peer lists live in temp-dir SQLite stores.

Worked figures come from ``test_steps_valuation``: TSLA FY2025 EPS 1.5,
EBITDA 27.5, FCF 28, so at $25 the P/E is 16.67 and the default DCF equity
value per share is 37.20. The F peer (net income 60 on 12 shares) has P/E
50.68 at the same price.
"""

import pytest

import api.main as main
from financial_analyst.numbers.prices import PriceStore
from financial_analyst.numbers.service import NumbersService, NumbersStore
from financial_analyst.steps.service import StepsService
from financial_analyst.steps.state import PeerStateStore, StepStateStore
from tests.auth_helpers import GENEROUS_LIMITS, build_client, signup_and_auth
from tests.fixtures.numbers import (
    ByCikFactsFetcher,
    F_TABLE,
    FULL_TABLE,
    FakeDownloader,
    FakePriceClient,
)
from tests.fixtures.xbrl_facts import make_facts

CIKS = {"TSLA": 1318605, "F": 1}
PRICE = 25.0
HISTORY = [
    {"date": "2021-12-31", "close": 20.0},
    {"date": "2022-12-30", "close": 30.0},
    {"date": "2023-12-29", "close": 40.0},
    {"date": "2024-12-31", "close": 30.0},
    {"date": "2025-12-31", "close": PRICE},
]


def make_services(tmp_path, monkeypatch, refresh=True, email="valuation@example.com"):
    numbers = NumbersService(
        downloader=FakeDownloader(CIKS),
        facts_fetcher=ByCikFactsFetcher(
            {1318605: make_facts(FULL_TABLE), 1: make_facts(F_TABLE)}
        ),
        price_client=FakePriceClient(current=PRICE, history=HISTORY),
        store=NumbersStore(str(tmp_path / "storage" / "numbers.json")),
        price_store=PriceStore(str(tmp_path / "storage" / "prices.json")),
    )
    if refresh:
        numbers.refresh("TSLA")
    db = str(tmp_path / "storage" / "steps.db")
    steps = StepsService(
        numbers_service=numbers,
        state_store=StepStateStore(db),
        peers_store=PeerStateStore(db),
    )
    monkeypatch.setattr(main, "_get_steps_service", lambda: steps)
    monkeypatch.setattr(main, "_get_numbers_service", lambda: numbers)
    client, _, _ = build_client(tmp_path, monkeypatch, limits=GENEROUS_LIMITS)
    signup_and_auth(client, email=email)
    return client, numbers, steps


class TestDoneStore:
    def test_set_and_get_done_round_trip(self, tmp_path):
        store = StepStateStore(str(tmp_path / "steps.db"))
        assert store.get_done_steps("a@example.com", "TSLA") == []
        store.set_done("a@example.com", "TSLA", 1)
        store.set_done("a@example.com", "TSLA", 3)
        assert store.get_done_steps("a@example.com", "TSLA") == [1, 3]

    def test_clear_done_removes_a_step(self, tmp_path):
        store = StepStateStore(str(tmp_path / "steps.db"))
        store.set_done("a@example.com", "TSLA", 1)
        store.clear_done("a@example.com", "TSLA", 1)
        assert store.get_done_steps("a@example.com", "TSLA") == []

    def test_done_is_scoped_to_user_and_ticker(self, tmp_path):
        store = StepStateStore(str(tmp_path / "steps.db"))
        store.set_done("a@example.com", "TSLA", 1)
        store.set_done("a@example.com", "MSFT", 2)
        assert store.get_done_steps("b@example.com", "TSLA") == []
        assert store.get_done_steps("a@example.com", "TSLA") == [1]
        assert store.get_done_steps("a@example.com", "MSFT") == [2]

    def test_done_is_per_user_between_users(self, tmp_path):
        store = StepStateStore(str(tmp_path / "steps.db"))
        store.set_done("a@example.com", "TSLA", 1)
        assert store.get_done_steps("b@example.com", "TSLA") == []


class TestDoneMarkApi:
    def test_done_mark_requires_auth(self, tmp_path, monkeypatch):
        client, _, _ = build_client(tmp_path, monkeypatch)
        assert client.post("/api/steps/TSLA/done/1").status_code == 401

    def test_mark_and_unmark_a_step(self, tmp_path, monkeypatch):
        client, _, _ = make_services(tmp_path, monkeypatch)
        resp = client.post("/api/steps/TSLA/done/1")
        assert resp.status_code == 200
        assert resp.json()["done"] == {
            "1": True, "2": False, "3": False, "4": False,
        }
        resp = client.delete("/api/steps/TSLA/done/1")
        assert resp.json()["done"]["1"] is False

    def test_done_is_per_user(self, tmp_path, monkeypatch):
        client_a, _, _ = make_services(tmp_path, monkeypatch, email="a@example.com")
        client_a.post("/api/steps/TSLA/done/1")
        client_b, _, _ = make_services(
            tmp_path, monkeypatch, refresh=False, email="b@example.com"
        )
        assert client_b.get("/api/steps/TSLA/done").json()["done"]["1"] is False

    def test_done_step_out_of_range_returns_422(self, tmp_path, monkeypatch):
        client, _, _ = make_services(tmp_path, monkeypatch)
        assert client.post("/api/steps/TSLA/done/5").status_code == 422
        assert client.post("/api/steps/TSLA/done/0").status_code == 422

    def test_done_404_when_numbers_missing(self, tmp_path, monkeypatch):
        client, _, _ = make_services(tmp_path, monkeypatch, refresh=False)
        assert client.post("/api/steps/TSLA/done/1").status_code == 404


class TestValuationGateApi:
    def test_valuation_locked_until_all_steps_done(self, tmp_path, monkeypatch):
        client, _, _ = make_services(tmp_path, monkeypatch)
        resp = client.get("/api/steps/TSLA/valuation")
        assert resp.status_code == 200
        body = resp.json()
        assert body["locked"] is True
        assert body["missing_steps"] == [1, 2, 3, 4]
        assert "valuation" not in body

        for step in (1, 2, 3):
            client.post(f"/api/steps/TSLA/done/{step}")
        body = client.get("/api/steps/TSLA/valuation").json()
        assert body["missing_steps"] == [4]

    def test_valuation_unlocks_when_all_done_and_computes(self, tmp_path, monkeypatch):
        client, _, _ = make_services(tmp_path, monkeypatch)
        for step in (1, 2, 3, 4):
            client.post(f"/api/steps/TSLA/done/{step}")
        resp = client.get("/api/steps/TSLA/valuation")
        assert resp.status_code == 200
        body = resp.json()
        assert body["locked"] is False
        assert body["missing_steps"] == []
        v = body["valuation"]
        assert v["dcf"]["equity_value_per_share"] == pytest.approx(37.20)
        assert v["multiples"]["pe"] == pytest.approx(PRICE / 1.5)
        assert v["history"][-1]["fiscal_year"] == 2025

    def test_valuation_requires_numbers(self, tmp_path, monkeypatch):
        client, _, _ = make_services(tmp_path, monkeypatch, refresh=False)
        assert client.get("/api/steps/TSLA/valuation").status_code == 404

    def test_valuation_requires_auth(self, tmp_path, monkeypatch):
        client, _, _ = build_client(tmp_path, monkeypatch)
        assert client.get("/api/steps/TSLA/valuation").status_code == 401

    def test_unmarking_a_step_relocks_valuation(self, tmp_path, monkeypatch):
        client, _, _ = make_services(tmp_path, monkeypatch)
        for step in (1, 2, 3, 4):
            client.post(f"/api/steps/TSLA/done/{step}")
        assert client.get("/api/steps/TSLA/valuation").json()["locked"] is False
        client.delete("/api/steps/TSLA/done/2")
        body = client.get("/api/steps/TSLA/valuation").json()
        assert body["locked"] is True
        assert body["missing_steps"] == [2]

    def test_valuation_accept_reject_gate_does_not_unlock(self, tmp_path, monkeypatch):
        """A step 1 'accept' is not a done mark: the valuation stays locked."""
        client, _, _ = make_services(tmp_path, monkeypatch)
        client.post("/api/steps/TSLA/gate", json={"decision": "accept"})
        body = client.get("/api/steps/TSLA/valuation").json()
        assert body["locked"] is True


class TestValuationAssumptions:
    def test_discount_rate_and_growth_overrides_flow_into_dcf(self, tmp_path, monkeypatch):
        client, _, _ = make_services(tmp_path, monkeypatch)
        for step in (1, 2, 3, 4):
            client.post(f"/api/steps/TSLA/done/{step}")
        resp = client.get(
            "/api/steps/TSLA/valuation", params={"discount_rate": 0.12, "growth": 0.05}
        )
        body = resp.json()
        assert body["valuation"]["dcf"]["discount_rate"] == pytest.approx(0.12)
        assert body["valuation"]["dcf"]["growth"] == pytest.approx(0.05)
        assert body["valuation"]["dcf"]["equity_value_per_share"] == pytest.approx(38.0)

    def test_price_override_recomputes_market_multiples(self, tmp_path, monkeypatch):
        client, _, _ = make_services(tmp_path, monkeypatch)
        for step in (1, 2, 3, 4):
            client.post(f"/api/steps/TSLA/done/{step}")
        baseline = client.get("/api/steps/TSLA/valuation").json()
        assert baseline["valuation"]["multiples"]["pe"] == pytest.approx(PRICE / 1.5)

        client.put("/api/numbers/TSLA/price", json={"price": 30.0})
        body = client.get("/api/steps/TSLA/valuation").json()
        assert body["valuation"]["multiples"]["price"] == pytest.approx(30.0)
        assert body["valuation"]["multiples"]["pe"] == pytest.approx(30.0 / 1.5)
        assert body["valuation"]["multiples"]["market_cap"] == pytest.approx(300.0)


class TestValuationPeers:
    def test_valuation_includes_peer_multiples(self, tmp_path, monkeypatch):
        client, numbers, _ = make_services(tmp_path, monkeypatch)
        client.put("/api/steps/TSLA/peers", json={"peers": ["F"]})
        assert numbers.price_store.get("F") is None
        for step in (1, 2, 3, 4):
            client.post(f"/api/steps/TSLA/done/{step}")
        body = client.get("/api/steps/TSLA/valuation").json()
        assert body["locked"] is False
        peers = body["valuation"]["peers"]
        assert [p["ticker"] for p in peers] == ["F"]
        assert peers[0]["pe"] == pytest.approx(PRICE / (60.0 / 12.0))
        assert numbers.price_store.get("F") is not None

    def test_valuation_without_peers_has_empty_peer_list(self, tmp_path, monkeypatch):
        client, _, _ = make_services(tmp_path, monkeypatch)
        for step in (1, 2, 3, 4):
            client.post(f"/api/steps/TSLA/done/{step}")
        body = client.get("/api/steps/TSLA/valuation").json()
        assert body["valuation"]["peers"] == []
