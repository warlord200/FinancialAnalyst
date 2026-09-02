"""Unit tests for the hybrid (BM25 + reciprocal rank fusion) retrieval legs.

The integration tests live in ``test_steps_retrieval.py``; these cover the
pure fusion math, the tokenizer, and the reranker seam with fake models so
no embedding or cross-encoder model is loaded.
"""

import pytest
from llama_index.core import Settings
from llama_index.core.embeddings.mock_embed_model import MockEmbedding
from llama_index.core.llms import MockLLM
from llama_index.core.schema import TextNode

from financial_analyst.indexing.company_index import CompanyIndex
from financial_analyst.steps.retrieval import (
    CrossEncoderReranker,
    ScopedRetriever,
    SourceChunk,
    reciprocal_rank_fusion,
    tokenize,
)

ITEM_1_TEXT = "Tesla designs electric vehicles and sells them to consumers."
ITEM_1A_TEXT = "We face competition from other automakers."
ITEM_7_TEXT = "Revenue grew strongly in fiscal 2025."


def chunk(text, item="ITEM 1", fiscal_year=2025, ticker="TSLA", filing="10-K"):
    return SourceChunk(
        text=text, item=item, fiscal_year=fiscal_year, ticker=ticker, filing=filing
    )


class TestTokenizer:
    def test_lowercases_and_splits_alphanumeric(self):
        assert tokenize("We face competition — from 2 automakers.") == [
            "we",
            "face",
            "competition",
            "from",
            "2",
            "automakers",
        ]

    def test_empty_input(self):
        assert tokenize("") == []
        assert tokenize("!!! ???") == []


class TestReciprocalRankFusion:
    def test_doc_seen_by_both_legs_ranks_first(self):
        dense = [chunk(ITEM_1_TEXT), chunk(ITEM_1A_TEXT)]
        sparse = [chunk(ITEM_7_TEXT), chunk(ITEM_1_TEXT)]
        fused = reciprocal_rank_fusion(dense, sparse, k=1)
        assert fused[0].text == ITEM_1_TEXT
        assert len(fused) == 3

    def test_sparse_only_doc_outranks_second_dense_doc(self):
        dense = [chunk(ITEM_1_TEXT), chunk(ITEM_1A_TEXT)]
        sparse = [chunk(ITEM_7_TEXT), chunk(ITEM_1_TEXT)]
        fused = reciprocal_rank_fusion(dense, sparse, k=1)
        order = [c.text for c in fused]
        # ITEM_7 (sparse rank 1) beats ITEM_1A (dense rank 2 only)
        assert order.index(ITEM_7_TEXT) < order.index(ITEM_1A_TEXT)

    def test_duplicate_text_across_years_is_distinct(self):
        y25 = chunk(ITEM_1_TEXT, fiscal_year=2025)
        y24 = chunk(ITEM_1_TEXT, fiscal_year=2024)
        fused = reciprocal_rank_fusion([y25, y24], [y24], k=1)
        assert len(fused) == 2


class TestCrossEncoderReranker:
    def test_model_loads_lazily(self):
        reranker = CrossEncoderReranker("BAAI/bge-reranker-v2-m3")
        assert reranker._model is None

    def test_rerank_empty_returns_empty(self):
        reranker = CrossEncoderReranker("BAAI/bge-reranker-v2-m3")
        assert reranker.rerank("query", []) == []


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


NODES = [
    TextNode(
        text=ITEM_1_TEXT,
        metadata={"ticker": "TSLA", "fiscal_year": 2025, "item": "ITEM 1", "filing": "10-K"},
    ),
    TextNode(
        text=ITEM_1A_TEXT,
        metadata={"ticker": "TSLA", "fiscal_year": 2025, "item": "ITEM 1A", "filing": "10-K"},
    ),
    TextNode(
        text=ITEM_7_TEXT,
        metadata={"ticker": "TSLA", "fiscal_year": 2025, "item": "ITEM 7", "filing": "10-K"},
    ),
]


def make_index(tmp_path):
    index = CompanyIndex(
        chroma_path=str(tmp_path / "chroma"), storage_base=str(tmp_path / "storage")
    )
    index.build("TSLA", NODES)
    return index


def _dense_only(collection, query_embedding, where, n, ticker):
    return [chunk("The company sells electric vehicles.")]


class ReversingReranker:
    def rerank(self, query, chunks, top_n=None):
        rev = list(reversed(chunks))
        return rev[:top_n] if top_n is not None else rev


class TestHybridWiring:
    def test_hybrid_adds_keyword_doc_the_dense_leg_missed(self, tmp_path, mock_models, monkeypatch):
        retriever = ScopedRetriever(make_index(tmp_path))
        monkeypatch.setattr(retriever, "_query_dense", _dense_only)
        chunks = retriever.retrieve("TSLA", "competition from automakers", top_k=4)
        assert any("competition from other automakers" in c.text for c in chunks)

    def test_vector_only_mode_ignores_bm25(self, tmp_path, mock_models, monkeypatch):
        retriever = ScopedRetriever(make_index(tmp_path), use_hybrid=False)
        monkeypatch.setattr(retriever, "_query_dense", _dense_only)
        chunks = retriever.retrieve("TSLA", "competition from automakers", top_k=4)
        assert [c.text for c in chunks] == ["The company sells electric vehicles."]

    def test_reranker_reorders_fused_candidates_and_truncates(self, tmp_path, mock_models, monkeypatch):
        retriever = ScopedRetriever(make_index(tmp_path), reranker=ReversingReranker())
        dense = [chunk(ITEM_1_TEXT), chunk(ITEM_1A_TEXT), chunk(ITEM_7_TEXT)]
        monkeypatch.setattr(retriever, "_query_dense", lambda c, e, w, n, t: dense)
        monkeypatch.setattr(
            retriever, "_query_sparse", lambda c, q, w, n, t: []
        )
        chunks = retriever.retrieve("TSLA", "gibberish zzzqqq", top_k=2)
        assert [c.text for c in chunks] == [ITEM_7_TEXT, ITEM_1A_TEXT]

    def test_sparse_leg_scopes_to_items(self, tmp_path, mock_models):
        retriever = ScopedRetriever(make_index(tmp_path))
        # Only ITEM 1A mentions "automakers", and it is outside ITEM 7 scope
        chunks = retriever.retrieve(
            "TSLA", "automakers", items=["ITEM 7"], top_k=4
        )
        for c in chunks:
            assert c.item == "ITEM 7"
        assert not any("automakers" in c.text for c in chunks)
