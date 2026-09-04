"""Unit tests for the corpus snapshot (``corpus.py``).

The curated benchmark and smoke eval read the *live* ingested corpus — the
collection the retriever actually queries — rather than a re-embedded
scratch copy, so per-step scoring sees the same chunking, metadata, and
fiscal years production serves. ``snapshot`` reads one collection's chunks
and metadata into plain records; these tests pin that mapping and the
empty/missing-ticker behaviour.
"""

import pytest
from llama_index.core import Settings
from llama_index.core.embeddings.mock_embed_model import MockEmbedding
from llama_index.core.llms import MockLLM
from llama_index.core.schema import TextNode

from financial_analyst.evaluation.corpus import CorpusChunk, snapshot
from financial_analyst.indexing.company_index import CompanyIndex

NODES = [
    TextNode(
        text="Tesla designs electric vehicles.",
        metadata={"ticker": "TSLA", "fiscal_year": 2025, "item": "ITEM 1", "filing": "10-K"},
    ),
    TextNode(
        text="Revenue grew strongly.",
        metadata={"ticker": "TSLA", "fiscal_year": 2025, "item": "ITEM 7", "filing": "10-K"},
    ),
    TextNode(
        text="Risk factors from the prior year.",
        metadata={"ticker": "TSLA", "fiscal_year": 2024, "item": "ITEM 1A", "filing": "10-K"},
    ),
]


@pytest.fixture
def mock_models():
    old_embed, old_llm = Settings._embed_model, Settings._llm
    Settings.embed_model = MockEmbedding(embed_dim=8)
    Settings.llm = MockLLM()
    try:
        yield
    finally:
        Settings._embed_model = old_embed
        Settings._llm = old_llm


def make_index(tmp_path):
    index = CompanyIndex(
        chroma_path=str(tmp_path / "chroma"), storage_base=str(tmp_path / "storage")
    )
    index.build("TSLA", NODES)
    return index


def test_snapshot_reads_every_chunk_with_metadata(tmp_path, mock_models):
    chunks = snapshot(make_index(tmp_path), "TSLA")
    assert len(chunks) == 3
    by_text = {c.text: c for c in chunks}
    assert by_text["Tesla designs electric vehicles."] == CorpusChunk(
        chunk_id=by_text["Tesla designs electric vehicles."].chunk_id,
        text="Tesla designs electric vehicles.",
        item="ITEM 1",
        fiscal_year=2025,
        filing="10-K",
    )
    item_7 = by_text["Revenue grew strongly."]
    assert item_7.item == "ITEM 7"
    assert item_7.fiscal_year == 2025
    assert item_7.filing == "10-K"
    assert item_7.chunk_id


def test_snapshot_lowercases_ticker_lookup(tmp_path, mock_models):
    chunks = snapshot(make_index(tmp_path), "tsla")
    assert len(chunks) == 3


def test_snapshot_empty_when_ticker_not_ingested(tmp_path, mock_models):
    assert snapshot(make_index(tmp_path), "NOPE") == []
