"""Unit tests for the step-scoped chat service.

T8 chat answers must retrieve from the step's own source items by default,
lift to the whole corpus via the search-everything escape hatch, and carry
source citations derived from the cited passages. These tests exercise the
ChatService seam directly with a recording fake retriever and a fake LLM.
"""

import json

import pytest

from financial_analyst.steps.chat import ChatService, UnsupportedStepError
from financial_analyst.steps.generation import ArtifactValidationError, NoSourceError
from tests.fixtures.steps import (
    FakeLLM,
    FakeRetriever,
    ITEM_1A_TEXT,
    ITEM_1_TEXT,
    ITEM_5_TEXT,
    ITEM_7_TEXT,
    RecordingRetriever,
    make_all_items_corpus,
    valid_chat_json,
)


def fabricated_evidence_json():
    return json.dumps(
        {
            "answer": "The company does something.",
            "source_refs": [1],
            "evidence": ["This sentence is not in the source material at all."],
        }
    )


def bad_ref_json():
    return json.dumps(
        {
            "answer": "Tesla designs and manufactures electric vehicles.",
            "source_refs": [7],
            "evidence": ["Tesla designs and manufactures electric vehicles."],
        }
    )


def make_chat(retriever=None, llm=None):
    retriever = retriever or RecordingRetriever(make_all_items_corpus())
    return ChatService(retriever, llm or FakeLLM(valid_chat_json()))


class TestScoping:
    def test_step_2_scopes_retrieval_to_item_1_and_1a(self):
        retriever = RecordingRetriever(make_all_items_corpus())
        chat = make_chat(retriever=retriever)
        result = chat.answer("TSLA", "Who are the customers?", step=2)
        assert result["scope"]["items"] == ["ITEM 1", "ITEM 1A"]
        assert result["search_all"] is False
        assert retriever.retrieve_args[-1]["items"] == ["ITEM 1", "ITEM 1A"]

    def test_step_3_scopes_retrieval_to_item_7_and_8(self):
        retriever = RecordingRetriever(make_all_items_corpus())
        llm = FakeLLM(
            valid_chat_json(
                answer=ITEM_7_TEXT.split(". ")[0] + ".",
                refs=(1,),
                evidence=[ITEM_7_TEXT.split(". ")[0] + "."],
            )
        )
        chat = ChatService(retriever, llm)
        result = chat.answer("TSLA", "How profitable was the year?", step=3)
        assert result["scope"]["items"] == ["ITEM 7", "ITEM 8"]
        assert retriever.retrieve_args[-1]["items"] == ["ITEM 7", "ITEM 8"]

    def test_step_4_scopes_retrieval_to_item_5_and_7(self):
        retriever = RecordingRetriever(make_all_items_corpus())
        llm = FakeLLM(
            valid_chat_json(
                answer=ITEM_5_TEXT.split(". ")[0] + ".",
                refs=(1,),
                evidence=[ITEM_5_TEXT.split(". ")[0] + "."],
            )
        )
        chat = ChatService(retriever, llm)
        result = chat.answer("TSLA", "What is the financing plan?", step=4)
        assert result["scope"]["items"] == ["ITEM 5", "ITEM 7"]
        assert retriever.retrieve_args[-1]["items"] == ["ITEM 5", "ITEM 7"]

    def test_search_all_retrieves_whole_corpus(self):
        retriever = RecordingRetriever(make_all_items_corpus())
        chat = make_chat(retriever=retriever)
        result = chat.answer("TSLA", "Who are the customers?", step=2, search_all=True)
        assert result["search_all"] is True
        assert result["scope"]["items"] is None
        assert retriever.retrieve_args[-1]["items"] is None

    def test_step_without_defined_scope_is_rejected(self):
        chat = make_chat()
        for step in (1, 5, 6):
            with pytest.raises(UnsupportedStepError):
                chat.answer("TSLA", "Who are the customers?", step=step)

    def test_unsupported_step_is_rejected_even_with_search_all(self):
        chat = make_chat()
        with pytest.raises(UnsupportedStepError):
            chat.answer("TSLA", "Who are the customers?", step=6, search_all=True)


class TestAnswer:
    def test_answer_carries_source_citations(self):
        result = make_chat().answer("TSLA", "Who are the customers?", step=2)
        assert result["ticker"] == "TSLA"
        assert result["step"] == 2
        assert result["answer"]
        assert len(result["sources"]) >= 1
        first = result["sources"][0]
        assert first["text"] == ITEM_1_TEXT
        assert first["item"] == "ITEM 1"
        assert first["fiscal_year"] == 2025
        assert first["filing"] == "10-K"

    def test_sources_derive_only_from_cited_passages(self):
        llm = FakeLLM(valid_chat_json(refs=(2,)))
        chat = ChatService(RecordingRetriever(make_all_items_corpus()), llm)
        result = chat.answer("TSLA", "What are the risks?", step=2)
        assert len(result["sources"]) == 1
        assert result["sources"][0]["item"] == "ITEM 1A"
        assert result["sources"][0]["text"] == ITEM_1A_TEXT

    def test_evidence_is_returned_with_answer(self):
        result = make_chat().answer("TSLA", "Who are the customers?", step=2)
        assert result["evidence"]
        assert result["evidence"][0] == ITEM_1_TEXT.split(". ")[0] + "."


class TestGrounding:
    def test_ungrounded_answer_retries_then_raises(self):
        llm = FakeLLM("not json at all")
        chat = ChatService(RecordingRetriever(make_all_items_corpus()), llm)
        with pytest.raises(ArtifactValidationError) as exc:
            chat.answer("TSLA", "Who are the customers?", step=2)
        assert "chat" == exc.value.key
        assert llm.calls == 2

    def test_repair_prompt_is_sent_after_validation_failure(self):
        llm = FakeLLM(bad_ref_json(), valid_chat_json())
        chat = ChatService(RecordingRetriever(make_all_items_corpus()), llm)
        result = chat.answer("TSLA", "Who are the customers?", step=2)
        assert result["answer"]
        assert llm.calls == 2
        assert "rejected" in llm.prompts[1]

    def test_fabricated_evidence_is_rejected(self):
        llm = FakeLLM(fabricated_evidence_json())
        chat = ChatService(RecordingRetriever(make_all_items_corpus()), llm)
        with pytest.raises(ArtifactValidationError):
            chat.answer("TSLA", "Who are the customers?", step=2)

    def test_accepts_markdown_fenced_json(self):
        fenced = f"```json\n{valid_chat_json()}\n```"
        chat = ChatService(RecordingRetriever(make_all_items_corpus()), FakeLLM(fenced))
        result = chat.answer("TSLA", "Who are the customers?", step=2)
        assert result["answer"]

    def test_raises_no_source_when_ticker_not_ingested(self):
        chat = ChatService(FakeRetriever(chunks=[], years=[]), FakeLLM(valid_chat_json()))
        with pytest.raises(NoSourceError):
            chat.answer("NOPE", "Who are the customers?", step=2)

    def test_raises_no_source_when_step_has_no_chunks(self):
        chat = ChatService(FakeRetriever(chunks=[], years=[2025]), FakeLLM(valid_chat_json()))
        with pytest.raises(NoSourceError):
            chat.answer("TSLA", "Who are the customers?", step=2)
