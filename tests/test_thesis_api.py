"""HTTP API tests for the Step 6 thesis (T12, revised for read-only).

The app under test is the real FastAPI app with a faked service boundary:
numbers come from a NumbersService backed by per-CIK facts and a price
client, per-user done-marks live in a temp-dir SQLite store, and the
thesis draft is produced by a real ArtifactGenerator over a fake corpus
with a fake LLM, so grounding is exercised end to end.

The thesis is hard-gated like valuation: it stays locked until the user
marks steps 1-4 done. Once unlocked, the grounded draft *is* the thesis:
the read-only document mirrors the draft's content under the canonical
headings, so there is no per-user save endpoint and no edit path.
"""

import pytest

import api.main as main
from financial_analyst.numbers.prices import PriceStore
from financial_analyst.numbers.service import NumbersService, NumbersStore
from financial_analyst.steps.drafts import DraftStore
from financial_analyst.steps.generation import ArtifactGenerator
from financial_analyst.steps.service import StepsService
from financial_analyst.steps.state import StepStateStore
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
        assert "thesis" not in body

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

    def test_thesis_doc_is_read_only_and_mirrors_the_draft(self, tmp_path, monkeypatch):
        """The thesis document is the draft under canonical headings: no
        edit surface, no saved/saved_at state."""
        client, _, _ = make_thesis_client(tmp_path, monkeypatch)
        mark_all_done(client)
        body = client.get("/api/steps/TSLA/thesis").json()
        thesis = body["thesis"]
        assert [s["key"] for s in thesis["sections"]] == EXPECTED_KEYS
        assert "saved" not in thesis
        assert "saved_at" not in thesis
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
        )
        monkeypatch.setattr(main, "_get_steps_service", lambda: empty_steps)
        assert client.get("/api/steps/TSLA/thesis").status_code == 404

    def test_save_endpoint_no_longer_exists(self, tmp_path, monkeypatch):
        """The thesis is read-only: the PUT save route is gone."""
        client, _, _ = make_thesis_client(tmp_path, monkeypatch)
        mark_all_done(client)
        resp = client.put(
            "/api/steps/TSLA/thesis",
            json={"sections": [{"key": "hold", "content": "x"}]},
        )
        assert resp.status_code == 405
