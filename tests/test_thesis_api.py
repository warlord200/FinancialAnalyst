"""HTTP API tests for the Step 6 thesis (T12).

The app under test is the real FastAPI app with a faked service boundary:
numbers come from a NumbersService backed by per-CIK facts and a price
client, per-user done-marks live in a temp-dir SQLite store, and the
thesis draft is produced by a real ArtifactGenerator over a fake corpus
with a fake LLM, so grounding is exercised end to end.

The thesis is hard-gated like valuation: it stays locked until the user
marks steps 1-4 done. Once unlocked, the generated draft seeds an
editable document that the user saves per (email, ticker); reopening the
ticker shows the saved text, and re-analysis (which rebuilds the shared
draft cache) never touches it.
"""

import pytest

import api.main as main
from financial_analyst.numbers.prices import PriceStore
from financial_analyst.numbers.service import NumbersService, NumbersStore
from financial_analyst.steps.drafts import DraftStore
from financial_analyst.steps.generation import ArtifactGenerator
from financial_analyst.steps.service import StepsService
from financial_analyst.steps.state import StepStateStore, ThesisStore
from financial_analyst.steps.thesis import thesis_section_keys
from tests.auth_helpers import GENEROUS_LIMITS, build_client, signup_and_auth
from tests.fixtures.numbers import FULL_TABLE, FakeDownloader, FakeFactsFetcher, FakePriceClient
from tests.fixtures.steps import FakeLLM, FakeRetriever, make_all_items_corpus, valid_section_json
from tests.fixtures.xbrl_facts import make_facts

EXPECTED_KEYS = thesis_section_keys()


def _numbers(tmp_path):
    return NumbersService(
        downloader=FakeDownloader({"TSLA": 1318605}),
        facts_fetcher=FakeFactsFetcher(make_facts(FULL_TABLE)),
        price_client=FakePriceClient(),
        store=NumbersStore(str(tmp_path / "storage" / "numbers.json")),
        price_store=PriceStore(str(tmp_path / "storage" / "prices.json")),
    )


def make_thesis_client(
    tmp_path,
    monkeypatch,
    llm=None,
    corpus=None,
    refresh=True,
    email="thesis@example.com",
):
    numbers = _numbers(tmp_path)
    if refresh:
        numbers.refresh("TSLA")
    retriever = FakeRetriever(corpus or make_all_items_corpus())
    llm = llm or FakeLLM(valid_section_json())
    generator = ArtifactGenerator(retriever, llm)
    steps = StepsService(
        numbers_service=numbers,
        state_store=StepStateStore(str(tmp_path / "storage" / "steps.db")),
        generator=generator,
        draft_store=DraftStore(str(tmp_path / "storage" / "drafts.json")),
        thesis_store=ThesisStore(str(tmp_path / "storage" / "steps.db")),
    )
    monkeypatch.setattr(main, "_get_numbers_service", lambda: numbers)
    monkeypatch.setattr(main, "_get_steps_service", lambda: steps)
    client, _, _ = build_client(tmp_path, monkeypatch, limits=GENEROUS_LIMITS)
    signup_and_auth(client, email=email)
    return client, steps, llm


def mark_all_done(client):
    for step in (1, 2, 3, 4):
        assert client.post(f"/api/steps/TSLA/done/{step}").status_code == 200


class TestThesisGate:
    def test_thesis_requires_auth(self, tmp_path, monkeypatch):
        client, _, _ = build_client(tmp_path, monkeypatch)
        assert client.get("/api/steps/TSLA/thesis").status_code == 401

    def test_thesis_locked_until_all_steps_done(self, tmp_path, monkeypatch):
        client, _, _ = make_thesis_client(tmp_path, monkeypatch)
        resp = client.get("/api/steps/TSLA/thesis")
        assert resp.status_code == 200
        body = resp.json()
        assert body["locked"] is True
        assert body["missing_steps"] == [1, 2, 3, 4]
        assert "thesis" not in body
        assert "draft" not in body

    def test_thesis_partially_unlocks_as_steps_done(self, tmp_path, monkeypatch):
        client, _, _ = make_thesis_client(tmp_path, monkeypatch)
        for step in (1, 2, 3):
            client.post(f"/api/steps/TSLA/done/{step}")
        body = client.get("/api/steps/TSLA/thesis").json()
        assert body["locked"] is True
        assert body["missing_steps"] == [4]

    def test_unmarking_a_step_relocks_thesis(self, tmp_path, monkeypatch):
        client, _, _ = make_thesis_client(tmp_path, monkeypatch)
        mark_all_done(client)
        assert client.get("/api/steps/TSLA/thesis").json()["locked"] is False
        client.delete("/api/steps/TSLA/done/2")
        body = client.get("/api/steps/TSLA/thesis").json()
        assert body["locked"] is True
        assert body["missing_steps"] == [2]

    def test_saved_thesis_stays_visible_when_relocked(self, tmp_path, monkeypatch):
        """Unmarking a step relocks drafting, but a saved thesis is the
        user's durable record and must not vanish."""
        client, _, _ = make_thesis_client(tmp_path, monkeypatch)
        mark_all_done(client)
        client.put(
            "/api/steps/TSLA/thesis",
            json={"sections": [{"key": "hold", "content": "My durable record."}]},
        )
        client.delete("/api/steps/TSLA/done/2")
        body = client.get("/api/steps/TSLA/thesis").json()
        assert body["locked"] is True
        assert body["missing_steps"] == [2]
        thesis = {s["key"]: s["content"] for s in body["thesis"]["sections"]}
        assert thesis["hold"] == "My durable record."

    def test_thesis_404_when_numbers_missing(self, tmp_path, monkeypatch):
        client, _, _ = make_thesis_client(tmp_path, monkeypatch, refresh=False)
        assert client.get("/api/steps/TSLA/thesis").status_code == 404


class TestThesisDraft:
    def test_unlocked_thesis_is_drafted_and_grounded(self, tmp_path, monkeypatch):
        client, _, _ = make_thesis_client(tmp_path, monkeypatch)
        mark_all_done(client)
        resp = client.get("/api/steps/TSLA/thesis")
        assert resp.status_code == 200
        body = resp.json()
        assert body["locked"] is False
        assert body["missing_steps"] == []
        draft = body["draft"]
        assert draft["artifact_type"] == "thesis"
        assert [s["key"] for s in draft["sections"]] == EXPECTED_KEYS
        for section in draft["sections"]:
            assert section["content"]
            assert len(section["sources"]) >= 1
            assert section["evidence"]

    def test_draft_seeds_the_editable_thesis_doc(self, tmp_path, monkeypatch):
        client, _, _ = make_thesis_client(tmp_path, monkeypatch)
        mark_all_done(client)
        body = client.get("/api/steps/TSLA/thesis").json()
        thesis = body["thesis"]
        assert thesis["saved"] is False
        assert thesis["saved_at"] is None
        assert [s["key"] for s in thesis["sections"]] == EXPECTED_KEYS
        draft_by_key = {s["key"]: s["content"] for s in body["draft"]["sections"]}
        for section in thesis["sections"]:
            assert section["content"] == draft_by_key[section["key"]]

    def test_draft_is_cached_after_first_generation(self, tmp_path, monkeypatch):
        client, _, llm = make_thesis_client(tmp_path, monkeypatch)
        mark_all_done(client)
        first = client.get("/api/steps/TSLA/thesis").json()
        calls_after_first = llm.calls
        second = client.get("/api/steps/TSLA/thesis").json()
        assert second["draft"] == first["draft"]
        assert llm.calls == calls_after_first

    def test_thesis_404_when_not_ingested(self, tmp_path, monkeypatch):
        client, _, _ = make_thesis_client(tmp_path, monkeypatch)
        mark_all_done(client)
        empty_steps = StepsService(
            numbers_service=_numbers(tmp_path),
            state_store=StepStateStore(str(tmp_path / "storage" / "steps.db")),
            generator=ArtifactGenerator(
                FakeRetriever(chunks=[], years=[]),
                FakeLLM(valid_section_json()),
            ),
            draft_store=DraftStore(str(tmp_path / "storage" / "drafts.json")),
            thesis_store=ThesisStore(str(tmp_path / "storage" / "steps.db")),
        )
        monkeypatch.setattr(main, "_get_steps_service", lambda: empty_steps)
        assert client.get("/api/steps/TSLA/thesis").status_code == 404


class TestThesisSave:
    def test_saved_thesis_persists_and_overrides_the_draft(self, tmp_path, monkeypatch):
        client, _, _ = make_thesis_client(tmp_path, monkeypatch)
        mark_all_done(client)
        put = client.put(
            "/api/steps/TSLA/thesis",
            json={
                "sections": [
                    {"key": "hold", "content": "I hold TSLA for the long run."},
                    {"key": "why", "content": "Because the filing shows a moat."},
                ]
            },
        )
        assert put.status_code == 200
        body = put.json()
        assert body["thesis"]["saved"] is True
        assert body["thesis"]["saved_at"]

        reopened = client.get("/api/steps/TSLA/thesis").json()
        thesis = {s["key"]: s["content"] for s in reopened["thesis"]["sections"]}
        assert thesis["hold"] == "I hold TSLA for the long run."
        assert thesis["why"] == "Because the filing shows a moat."
        assert reopened["thesis"]["saved"] is True

    def test_thesis_save_is_per_user(self, tmp_path, monkeypatch):
        client_a, _, _ = make_thesis_client(
            tmp_path, monkeypatch, refresh=True, email="a@example.com"
        )
        mark_all_done(client_a)
        client_a.put(
            "/api/steps/TSLA/thesis",
            json={"sections": [{"key": "hold", "content": "A's holding."}]},
        )

        client_b, _, _ = make_thesis_client(
            tmp_path, monkeypatch, refresh=False, email="b@example.com"
        )
        mark_all_done(client_b)
        body = client_b.get("/api/steps/TSLA/thesis").json()
        thesis = {s["key"]: s["content"] for s in body["thesis"]["sections"]}
        assert thesis["hold"] != "A's holding."
        assert body["thesis"]["saved"] is False

    def test_thesis_survives_reanalysis(self, tmp_path, monkeypatch):
        """Rebuilding the shared draft cache (as re-analysis would) keeps
        the saved thesis: reopening returns the user's own text."""
        client, _, _ = make_thesis_client(tmp_path, monkeypatch)
        mark_all_done(client)
        client.put(
            "/api/steps/TSLA/thesis",
            json={"sections": [{"key": "hold", "content": "Durable thesis text."}]},
        )

        reanalysed = StepsService(
            numbers_service=_numbers(tmp_path),
            state_store=StepStateStore(str(tmp_path / "storage" / "steps.db")),
            generator=ArtifactGenerator(
                FakeRetriever(make_all_items_corpus()),
                FakeLLM("{\"content\": \"a totally different draft\", \"source_refs\": [1], \"evidence\": [\"Tesla designs and manufactures electric vehicles and energy storage products.\"]}"),
            ),
            draft_store=DraftStore(str(tmp_path / "storage" / "reanalysed-drafts.json")),
            thesis_store=ThesisStore(str(tmp_path / "storage" / "steps.db")),
        )
        monkeypatch.setattr(main, "_get_steps_service", lambda: reanalysed)
        body = client.get("/api/steps/TSLA/thesis").json()
        thesis = {s["key"]: s["content"] for s in body["thesis"]["sections"]}
        assert body["thesis"]["saved"] is True
        assert thesis["hold"] == "Durable thesis text."

    def test_save_404_when_numbers_missing(self, tmp_path, monkeypatch):
        client, _, _ = make_thesis_client(tmp_path, monkeypatch, refresh=False)
        resp = client.put(
            "/api/steps/TSLA/thesis",
            json={"sections": [{"key": "hold", "content": "x"}]},
        )
        assert resp.status_code == 404

    def test_save_rejects_unknown_section_keys(self, tmp_path, monkeypatch):
        client, _, _ = make_thesis_client(tmp_path, monkeypatch)
        mark_all_done(client)
        resp = client.put(
            "/api/steps/TSLA/thesis",
            json={"sections": [{"key": "nonsense", "content": "x"}]},
        )
        assert resp.status_code == 422

    def test_service_save_drops_non_canonical_keys(self, tmp_path, monkeypatch):
        """The store keeps only canonical sections even when the service is
        called directly, past the route's 422 gate."""
        client, steps, _ = make_thesis_client(tmp_path, monkeypatch)
        steps.save_thesis(
            "thesis@example.com",
            "TSLA",
            [
                {"key": "hold", "content": "Kept."},
                {"key": "nonsense", "content": "Dropped."},
            ],
        )
        doc = steps.thesis_store.get("thesis@example.com", "TSLA")
        assert doc["content"] == {"hold": "Kept."}

    def test_save_requires_auth(self, tmp_path, monkeypatch):
        client, _, _ = build_client(tmp_path, monkeypatch)
        resp = client.put(
            "/api/steps/TSLA/thesis",
            json={"sections": [{"key": "hold", "content": "x"}]},
        )
        assert resp.status_code == 401
