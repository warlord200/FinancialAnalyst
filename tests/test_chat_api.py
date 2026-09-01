"""HTTP API tests for the step-scoped chat endpoint.

T8 chat is exercised through the API like the other steps: an authenticated
call to POST /api/steps/{ticker}/chat answers a question scoped to the
step's items (or the whole corpus when search_all is set), carries source
citations, and is gated by the per-day chat quota.
"""

import pytest

import api.main as main
from financial_analyst.numbers.prices import PriceStore
from financial_analyst.numbers.service import NumbersService, NumbersStore
from financial_analyst.steps.chat import ChatService
from financial_analyst.steps.retrieval import EmbedModelMismatchError
from financial_analyst.steps.service import StepsService
from financial_analyst.steps.state import StepStateStore
from tests.auth_helpers import GENEROUS_LIMITS, build_client, signup_and_auth
from tests.fixtures.numbers import FULL_TABLE, FakeDownloader, FakeFactsFetcher, FakePriceClient
from tests.fixtures.steps import (
    FakeLLM,
    FakeRetriever,
    RecordingRetriever,
    make_all_items_corpus,
    valid_chat_json,
)
from tests.fixtures.xbrl_facts import make_facts


def make_chat_client(tmp_path, monkeypatch, llm=None, retriever=None, limits=GENEROUS_LIMITS):
    numbers = NumbersService(
        downloader=FakeDownloader({"TSLA": 1318605}),
        facts_fetcher=FakeFactsFetcher(make_facts(FULL_TABLE)),
        price_client=FakePriceClient(),
        store=NumbersStore(str(tmp_path / "storage" / "numbers.json")),
        price_store=PriceStore(str(tmp_path / "storage" / "prices.json")),
    )
    retriever = retriever or RecordingRetriever(make_all_items_corpus())
    llm = llm or FakeLLM(valid_chat_json())
    chat = ChatService(retriever, llm)
    steps = StepsService(
        numbers_service=numbers,
        state_store=StepStateStore(str(tmp_path / "storage" / "steps.db")),
        chat_service=chat,
    )
    monkeypatch.setattr(main, "_get_steps_service", lambda: steps)
    client, _, _ = build_client(tmp_path, monkeypatch, limits=limits)
    signup_and_auth(client, email="steps@example.com")
    return client, steps, llm, retriever


def chat_json(step=2, question="Who are the customers?", search_all=False):
    return {"step": step, "question": question, "search_all": search_all}


class TestChat:
    def test_chat_answers_with_source_citations(self, tmp_path, monkeypatch):
        client, _, _, _ = make_chat_client(tmp_path, monkeypatch)
        resp = client.post("/api/steps/TSLA/chat", json=chat_json())
        assert resp.status_code == 200
        body = resp.json()
        assert body["ticker"] == "TSLA"
        assert body["step"] == 2
        assert body["search_all"] is False
        assert body["scope"]["items"] == ["ITEM 1", "ITEM 1A"]
        assert body["answer"]
        assert body["evidence"]
        assert len(body["sources"]) >= 1
        assert body["sources"][0]["item"] == "ITEM 1"

    def test_chat_scopes_retrieval_to_step_items_by_default(self, tmp_path, monkeypatch):
        client, _, _, retriever = make_chat_client(tmp_path, monkeypatch)
        client.post("/api/steps/TSLA/chat", json=chat_json(step=4))
        assert retriever.retrieve_args[-1]["items"] == ["ITEM 5", "ITEM 7"]

    def test_chat_search_all_searches_whole_corpus(self, tmp_path, monkeypatch):
        client, _, _, retriever = make_chat_client(tmp_path, monkeypatch)
        resp = client.post(
            "/api/steps/TSLA/chat",
            json=chat_json(step=2, search_all=True),
        )
        assert resp.status_code == 200
        assert resp.json()["search_all"] is True
        assert resp.json()["scope"]["items"] is None
        assert retriever.retrieve_args[-1]["items"] is None

    def test_chat_requires_auth(self, tmp_path, monkeypatch):
        client, _, _ = build_client(tmp_path, monkeypatch)
        resp = client.post("/api/steps/TSLA/chat", json=chat_json())
        assert resp.status_code == 401

    def test_chat_empty_question_returns_400(self, tmp_path, monkeypatch):
        client, _, _, _ = make_chat_client(tmp_path, monkeypatch)
        resp = client.post("/api/steps/TSLA/chat", json=chat_json(question="   "))
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"]

    def test_chat_unsupported_step_returns_400(self, tmp_path, monkeypatch):
        client, _, _, _ = make_chat_client(tmp_path, monkeypatch)
        resp = client.post("/api/steps/TSLA/chat", json=chat_json(step=6))
        assert resp.status_code == 400
        assert "not supported" in resp.json()["detail"]
        quota = client.get("/api/auth/quota").json()["chat"]
        assert quota["used"] == 0

    def test_chat_404_when_not_ingested(self, tmp_path, monkeypatch):
        client, _, _, _ = make_chat_client(
            tmp_path, monkeypatch, retriever=FakeRetriever(chunks=[], years=[])
        )
        resp = client.post("/api/steps/TSLA/chat", json=chat_json())
        assert resp.status_code == 404

    def test_chat_429_when_chat_quota_exhausted(self, tmp_path, monkeypatch):
        limits = {
            "analyses": {"verified": 100, "unverified": 100},
            "chat": {"verified": 1, "unverified": 1},
        }
        client, _, _, _ = make_chat_client(tmp_path, monkeypatch, limits=limits)
        assert client.post("/api/steps/TSLA/chat", json=chat_json()).status_code == 200
        resp = client.post("/api/steps/TSLA/chat", json=chat_json(question="Again?"))
        assert resp.status_code == 429

    def test_chat_consumes_chat_quota(self, tmp_path, monkeypatch):
        client, _, _, _ = make_chat_client(tmp_path, monkeypatch)
        client.post("/api/steps/TSLA/chat", json=chat_json())
        quota = client.get("/api/auth/quota").json()["chat"]
        assert quota["used"] == 1

    def test_chat_502_when_llm_cannot_ground(self, tmp_path, monkeypatch):
        client, _, _, _ = make_chat_client(tmp_path, monkeypatch, llm=FakeLLM("not json at all"))
        resp = client.post("/api/steps/TSLA/chat", json=chat_json())
        assert resp.status_code == 502
        assert "grounded" in resp.json()["detail"]

    def test_chat_refunds_quota_when_ungrounded(self, tmp_path, monkeypatch):
        client, _, _, _ = make_chat_client(tmp_path, monkeypatch, llm=FakeLLM("not json at all"))
        client.post("/api/steps/TSLA/chat", json=chat_json())
        quota = client.get("/api/auth/quota").json()["chat"]
        assert quota["used"] == 0

    def test_chat_503_on_embedding_model_mismatch(self, tmp_path, monkeypatch):
        from types import SimpleNamespace

        def boom(email, ticker, step, question, search_all=False):
            raise EmbedModelMismatchError(2560)

        monkeypatch.setattr(
            main,
            "_get_steps_service",
            lambda: SimpleNamespace(chat=boom),
        )
        client, _, _ = build_client(tmp_path, monkeypatch, limits=GENEROUS_LIMITS)
        signup_and_auth(client, email="steps@example.com")
        resp = client.post("/api/steps/TSLA/chat", json=chat_json())
        assert resp.status_code == 503
        assert "2560-dimensional" in resp.json()["detail"]
