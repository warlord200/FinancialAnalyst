# tests/test_report_generator.py
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from financial_analyst.analysis.report_generator import ReportGenerator


class FakeIndex:
    """Mimics a CustomDocs' query engines."""

    def __init__(self, responses):
        self._responses = responses

    def as_query_engine(self, **kwargs):
        return FakeQueryEngine(self._responses)


class FakeQueryEngine:
    def __init__(self, responses):
        self._responses = responses

    def query(self, query: str):
        text = MagicMock()
        text.response = self._responses.get(query, "canned answer with (Item 7) citation")
        return text


class FakeLLM:
    def complete(self, prompt: str):
        result = MagicMock()
        result.text = '{"label": "bullish", "score": 72, "rationale": "Strong growth."}'
        return result


def make_custom_docs(responses):
    cd = MagicMock()
    cd.get_indexes.return_value = (FakeIndex(responses), FakeIndex(responses))
    return cd


def test_generate_builds_full_report():
    docs_by_year = {
        2025: make_custom_docs({"canned": "Revenue grew 20% (Item 7)."}),
        2024: make_custom_docs({"canned": "Revenue grew 10% (Item 7)."}),
    }
    rg = ReportGenerator(docs_by_year, FakeLLM(), "TSLA")
    report = rg.generate()

    assert report.ticker == "TSLA"
    assert report.fiscal_years == [2025, 2024]
    assert report.verdict["label"] == "bullish"
    assert report.verdict["score"] == 72
    assert report.verdict["rationale"]
    assert "# Executive Summary" in report.markdown
    assert "# Business Overview" in report.markdown
    assert "# Risk Factors" in report.markdown
    assert "# MD&A" in report.markdown
    assert "# Segment Performance" in report.markdown
    assert "# YoY Trend Comparison" in report.markdown
    assert "# Financial Health" in report.markdown
    assert "# Data Provenance" in report.markdown
    assert "TSLA" in report.markdown


def test_generate_verdict_defaults_when_llm_returns_garbage():
    class GarbageLLM:
        def complete(self, prompt: str):
            result = MagicMock()
            result.text = "I have no idea."
            return result

    rg = ReportGenerator(
        {2025: make_custom_docs({}), 2024: make_custom_docs({})}, GarbageLLM(), "TSLA"
    )
    report = rg.generate()
    assert report.verdict["label"] in {"bullish", "neutral", "bearish"}
    assert 0 <= report.verdict["score"] <= 100
    assert report.verdict["rationale"]


def test_generate_handles_single_filing():
    rg = ReportGenerator({2025: make_custom_docs({})}, FakeLLM(), "AAPL")
    report = rg.generate()
    assert report.fiscal_years == [2025]
    assert "prior year unavailable" in report.markdown.lower() or "2024" not in report.markdown
