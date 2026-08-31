"""Shared test doubles for the steps layer: a representative Item 1/1A
corpus, a fake scoped retriever, and a fake LLM.

The corpus text is a set of deliberately quotable sentences so the fake
LLM can return evidence that the framework's verbatim grounding check
accepts. ``valid_section_json`` mirrors the LLM contract used by the
artifact generation framework (content, sources, evidence).
"""

import json
from types import SimpleNamespace

from financial_analyst.steps.retrieval import SourceChunk

ITEM_1_TEXT = (
    "Tesla designs and manufactures electric vehicles and energy storage products. "
    "It sells vehicles directly to consumers and reports two segments: automotive and energy generation. "
    "Revenue is largely one-off vehicle sales with some recurring software services. "
    "Key suppliers provide battery cells and raw materials for vehicles. "
    "Management believes its vertical integration is a competitive strength. "
    "The company is subject to regulation by the SEC, EPA, and NHTSA."
)

ITEM_1A_TEXT = (
    "We face significant competition from other automakers. "
    "Our business depends on suppliers and could be harmed by supply chain disruptions. "
    "Regulatory changes could increase our costs."
)


def make_corpus(year=2025, ticker="TSLA"):
    return [
        SourceChunk(text=ITEM_1_TEXT, item="ITEM 1", fiscal_year=year, ticker=ticker, filing="10-K"),
        SourceChunk(text=ITEM_1A_TEXT, item="ITEM 1A", fiscal_year=year, ticker=ticker, filing="10-K"),
    ]


def valid_section_json(content=ITEM_1_TEXT.split(". ")[0] + ".", evidence=None):
    return json.dumps(
        {
            "content": content,
            "sources": [
                {"type": "item", "value": "ITEM 1"},
                {"type": "fiscal_year", "value": "2025"},
            ],
            "evidence": evidence
            if evidence is not None
            else [ITEM_1_TEXT.split(". ")[0] + "."],
        }
    )


class FakeRetriever:
    def __init__(self, chunks=None, years=(2025,)):
        self.chunks = chunks if chunks is not None else make_corpus()
        self.years = list(years)
        self.retrieve_calls = 0

    def fiscal_years(self, ticker):
        return self.years

    def retrieve(self, ticker, query, items=None, fiscal_year=None, top_k=None):
        self.retrieve_calls += 1
        return [
            c
            for c in self.chunks
            if (items is None or c.item in items)
            and (fiscal_year is None or c.fiscal_year == fiscal_year)
        ]


class FakeLLM:
    def __init__(self, *responses):
        self.responses = [r for r in responses] if responses else [valid_section_json()]
        self.prompts = []
        self.calls = 0

    def complete(self, prompt):
        self.prompts.append(prompt)
        self.calls += 1
        return SimpleNamespace(text=self.responses[(self.calls - 1) % len(self.responses)])
