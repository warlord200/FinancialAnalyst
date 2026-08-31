import pytest

import api.main as main
from financial_analyst.numbers.prices import PriceStore
from financial_analyst.numbers.service import NumbersService, NumbersStore
from financial_analyst.steps.drafts import DraftStore
from financial_analyst.steps.generation import ArtifactGenerator
from financial_analyst.steps.retrieval import EmbedModelMismatchError
from financial_analyst.steps.service import StepsService
from financial_analyst.steps.state import StepStateStore
from tests.auth_helpers import GENEROUS_LIMITS, build_client, signup_and_auth
from tests.fixtures.numbers import FULL_TABLE, FakeDownloader, FakeFactsFetcher, FakePriceClient
from tests.fixtures.steps import FakeLLM, FakeRetriever
from tests.fixtures.xbrl_facts import make_facts


def make_business_client(tmp_path, monkeypatch, llm=None, retriever=None):
    numbers = NumbersService(
        downloader=FakeDownloader({"TSLA": 1318605}),
        facts_fetcher=FakeFactsFetcher(make_facts(FULL_TABLE)),
        price_client=FakePriceClient(),
        store=NumbersStore(str(tmp_path / "storage" / "numbers.json")),
        price_store=PriceStore(str(tmp_path / "storage" / "prices.json")),
    )
    retriever = retriever or FakeRetriever()
    llm = llm or FakeLLM()
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
    signup_and_auth(client, email="steps@example.com")
    return client, steps, llm


class TestBusinessSwot:
    def test_business_swot_renders_artifact_with_source_tags(self, tmp_path, monkeypatch):
        client, _, _ = make_business_client(tmp_path, monkeypatch)
        resp = client.get("/api/steps/TSLA/business-swot")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ticker"] == "TSLA"
        assert body["cached"] is False
        artifact = body["artifact"]
        assert artifact["artifact_type"] == "business_swot"
        assert artifact["fiscal_year"] == 2025
        assert artifact["scope"]["items"] == ["ITEM 1", "ITEM 1A"]
        assert artifact["sections"][0]["heading"] == "Business Overview"
        for section in artifact["sections"]:
            assert section["content"]
            assert len(section["sources"]) >= 1
        keys = [s["key"] for s in artifact["sections"]]
        assert keys[-4:] == ["swot_strengths", "swot_weaknesses", "swot_opportunities", "swot_threats"]

    def test_business_swot_is_cached_after_first_generation(self, tmp_path, monkeypatch):
        client, _, llm = make_business_client(tmp_path, monkeypatch)
        first = client.get("/api/steps/TSLA/business-swot")
        assert first.status_code == 200
        assert first.json()["cached"] is False
        calls_after_first = llm.calls
        second = client.get("/api/steps/TSLA/business-swot")
        assert second.status_code == 200
        assert second.json()["cached"] is True
        assert second.json()["artifact"] == first.json()["artifact"]
        assert llm.calls == calls_after_first

    def test_business_swot_cache_is_shared_across_users(self, tmp_path, monkeypatch):
        client, _, llm = make_business_client(tmp_path, monkeypatch)
        client.get("/api/steps/TSLA/business-swot")
        bob_client, _, _ = build_client(tmp_path, monkeypatch, limits=GENEROUS_LIMITS)
        signup_and_auth(bob_client, email="bob@example.com")
        resp = bob_client.get("/api/steps/TSLA/business-swot")
        assert resp.status_code == 200
        assert resp.json()["cached"] is True

    def test_business_swot_404_when_not_ingested(self, tmp_path, monkeypatch):
        client, _, _ = make_business_client(
            tmp_path, monkeypatch, retriever=FakeRetriever(chunks=[], years=[])
        )
        assert client.get("/api/steps/TSLA/business-swot").status_code == 404

    def test_business_swot_requires_auth(self, tmp_path, monkeypatch):
        client, _, _ = build_client(tmp_path, monkeypatch)
        assert client.get("/api/steps/TSLA/business-swot").status_code == 401

    def test_business_swot_502_when_llm_cannot_ground(self, tmp_path, monkeypatch):
        client, _, _ = make_business_client(
            tmp_path, monkeypatch, llm=FakeLLM("not json at all")
        )
        resp = client.get("/api/steps/TSLA/business-swot")
        assert resp.status_code == 502
        assert "grounded" in resp.json()["detail"]

    def test_business_swot_503_on_embedding_model_mismatch(self, tmp_path, monkeypatch):
        from types import SimpleNamespace

        def boom(email, ticker):
            raise EmbedModelMismatchError(2560)

        monkeypatch.setattr(
            main,
            "_get_steps_service",
            lambda: SimpleNamespace(business_swot=boom),
        )
        client, _, _ = build_client(tmp_path, monkeypatch, limits=GENEROUS_LIMITS)
        signup_and_auth(client, email="steps@example.com")
        resp = client.get("/api/steps/TSLA/business-swot")
        assert resp.status_code == 503
        assert "2560-dimensional" in resp.json()["detail"]
