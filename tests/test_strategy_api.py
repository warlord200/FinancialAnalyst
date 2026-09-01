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
from tests.fixtures.steps import FakeLLM, FakeRetriever, make_strategy_corpus, valid_strategy_section_json
from tests.fixtures.xbrl_facts import make_facts


def make_strategy_client(tmp_path, monkeypatch, llm=None, retriever=None, refresh=True):
    numbers = NumbersService(
        downloader=FakeDownloader({"TSLA": 1318605}),
        facts_fetcher=FakeFactsFetcher(make_facts(FULL_TABLE)),
        price_client=FakePriceClient(),
        store=NumbersStore(str(tmp_path / "storage" / "numbers.json")),
        price_store=PriceStore(str(tmp_path / "storage" / "prices.json")),
    )
    if refresh:
        numbers.refresh("TSLA")
    retriever = retriever or FakeRetriever(make_strategy_corpus())
    llm = llm or FakeLLM(valid_strategy_section_json())
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


class TestStrategy:
    def test_strategy_renders_sections_and_returns_table(self, tmp_path, monkeypatch):
        client, _, _ = make_strategy_client(tmp_path, monkeypatch)
        resp = client.get("/api/steps/TSLA/strategy")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ticker"] == "TSLA"
        assert body["cached"] is False
        artifact = body["artifact"]
        assert artifact["artifact_type"] == "strategy"
        assert artifact["fiscal_year"] == 2025
        assert artifact["scope"]["items"] == ["ITEM 5", "ITEM 7"]
        assert [s["key"] for s in artifact["sections"]] == ["plan", "capex", "financing"]
        for section in artifact["sections"]:
            assert section["content"]
            assert len(section["sources"]) >= 1
            assert section["evidence"]
        returns = artifact["returns"]
        assert returns["key"] == "returns"
        assert {r["label"] for r in returns["rows"]} == {"ROIC", "ROE", "ROCE"}
        roe_row = next(r for r in returns["rows"] if r["label"] == "ROE")
        assert roe_row["values"]["2025"] == pytest.approx(0.12)
        assert {"type": "xbrl_fact", "value": "NetIncomeLoss"} in roe_row["sources"]

    def test_strategy_is_cached_after_first_generation(self, tmp_path, monkeypatch):
        client, _, llm = make_strategy_client(tmp_path, monkeypatch)
        first = client.get("/api/steps/TSLA/strategy")
        assert first.status_code == 200
        assert first.json()["cached"] is False
        calls_after_first = llm.calls
        second = client.get("/api/steps/TSLA/strategy")
        assert second.status_code == 200
        assert second.json()["cached"] is True
        assert second.json()["artifact"] == first.json()["artifact"]
        assert llm.calls == calls_after_first

    def test_strategy_404_when_numbers_missing(self, tmp_path, monkeypatch):
        client, _, _ = make_strategy_client(tmp_path, monkeypatch, refresh=False)
        assert client.get("/api/steps/TSLA/strategy").status_code == 404

    def test_strategy_404_when_not_ingested(self, tmp_path, monkeypatch):
        client, _, _ = make_strategy_client(
            tmp_path, monkeypatch, retriever=FakeRetriever(chunks=[], years=[])
        )
        assert client.get("/api/steps/TSLA/strategy").status_code == 404

    def test_strategy_uses_latest_year_with_all_requested_items(self, tmp_path, monkeypatch):
        from tests.fixtures.steps import ITEM_1_TEXT, ITEM_5_TEXT, ITEM_7_TEXT, SourceChunk

        corpus = [
            SourceChunk(text=ITEM_5_TEXT, item="ITEM 5", fiscal_year=2026, ticker="TSLA", filing="10-Q"),
            SourceChunk(text=ITEM_1_TEXT, item="ITEM 1", fiscal_year=2026, ticker="TSLA", filing="10-Q"),
            SourceChunk(text=ITEM_5_TEXT, item="ITEM 5", fiscal_year=2025, ticker="TSLA", filing="10-K"),
            SourceChunk(text=ITEM_7_TEXT, item="ITEM 7", fiscal_year=2025, ticker="TSLA", filing="10-K"),
        ]
        client, _, _ = make_strategy_client(
            tmp_path, monkeypatch, retriever=FakeRetriever(chunks=corpus, years=(2026, 2025))
        )
        resp = client.get("/api/steps/TSLA/strategy")
        assert resp.status_code == 200
        artifact = resp.json()["artifact"]
        assert artifact["fiscal_year"] == 2025
        assert ("fiscal_year", "2025") in [
            (t["type"], t["value"]) for t in artifact["sections"][0]["sources"]
        ]

    def test_strategy_requires_auth(self, tmp_path, monkeypatch):
        client, _, _ = build_client(tmp_path, monkeypatch)
        assert client.get("/api/steps/TSLA/strategy").status_code == 401

    def test_strategy_502_when_llm_cannot_ground(self, tmp_path, monkeypatch):
        client, _, _ = make_strategy_client(
            tmp_path, monkeypatch, llm=FakeLLM("not json at all")
        )
        resp = client.get("/api/steps/TSLA/strategy")
        assert resp.status_code == 502
        assert "grounded" in resp.json()["detail"]

    def test_strategy_503_on_embedding_model_mismatch(self, tmp_path, monkeypatch):
        from types import SimpleNamespace

        def boom(email, ticker):
            raise EmbedModelMismatchError(2560)

        monkeypatch.setattr(
            main,
            "_get_steps_service",
            lambda: SimpleNamespace(strategy=boom),
        )
        client, _, _ = build_client(tmp_path, monkeypatch, limits=GENEROUS_LIMITS)
        signup_and_auth(client, email="steps@example.com")
        resp = client.get("/api/steps/TSLA/strategy")
        assert resp.status_code == 503
        assert "2560-dimensional" in resp.json()["detail"]
