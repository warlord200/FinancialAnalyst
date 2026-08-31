import pytest
from llama_index.core import Settings
from llama_index.core.embeddings.mock_embed_model import MockEmbedding
from llama_index.core.llms import MockLLM
from llama_index.core.schema import TextNode

from financial_analyst.indexing.company_index import CompanyIndex
from financial_analyst.steps.retrieval import EmbedModelMismatchError, ScopedRetriever

NODES = [
    TextNode(
        text="Tesla designs electric vehicles and sells them to consumers.",
        metadata={"ticker": "TSLA", "fiscal_year": 2025, "item": "ITEM 1", "filing": "10-K"},
    ),
    TextNode(
        text="We face competition from other automakers.",
        metadata={"ticker": "TSLA", "fiscal_year": 2025, "item": "ITEM 1A", "filing": "10-K"},
    ),
    TextNode(
        text="Revenue grew strongly in fiscal 2025.",
        metadata={"ticker": "TSLA", "fiscal_year": 2025, "item": "ITEM 7", "filing": "10-K"},
    ),
    TextNode(
        text="Business summary from the prior year.",
        metadata={"ticker": "TSLA", "fiscal_year": 2024, "item": "ITEM 1", "filing": "10-K"},
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


def test_retrieve_scopes_to_items_and_fiscal_year(tmp_path, mock_models):
    retriever = ScopedRetriever(make_index(tmp_path))
    chunks = retriever.retrieve(
        "TSLA", "business and competition", items=["ITEM 1", "ITEM 1A"], fiscal_year=2025
    )
    assert chunks
    for c in chunks:
        assert c.item in {"ITEM 1", "ITEM 1A"}
        assert c.fiscal_year == 2025
        assert c.ticker == "TSLA"
        assert c.filing == "10-K"
        assert c.text


def test_retrieve_without_scope_returns_any_item_or_year(tmp_path, mock_models):
    retriever = ScopedRetriever(make_index(tmp_path))
    chunks = retriever.retrieve("TSLA", "revenue grew")
    assert any(c.item == "ITEM 7" for c in chunks)
    assert any(c.fiscal_year == 2024 for c in chunks)


def test_retrieve_returns_empty_when_ticker_not_ingested(tmp_path, mock_models):
    retriever = ScopedRetriever(make_index(tmp_path))
    assert retriever.retrieve("NOPE", "anything") == []


def test_fiscal_years_returns_sorted_years(tmp_path, mock_models):
    retriever = ScopedRetriever(make_index(tmp_path))
    assert retriever.fiscal_years("TSLA") == [2025, 2024]


def test_fiscal_years_empty_when_not_ingested(tmp_path, mock_models):
    retriever = ScopedRetriever(make_index(tmp_path))
    assert retriever.fiscal_years("NOPE") == []


def test_build_records_embedding_metadata(tmp_path, mock_models):
    index = make_index(tmp_path)
    collection = index.collection("TSLA")
    assert collection.metadata["embed_dim"] == 8
    assert collection.metadata["embed_model"]


def test_retrieve_raises_clear_error_on_embedding_dim_mismatch(tmp_path, mock_models):
    index = make_index(tmp_path)
    retriever = ScopedRetriever(index)
    old = Settings.embed_model
    Settings.embed_model = MockEmbedding(embed_dim=4)
    try:
        with pytest.raises(EmbedModelMismatchError) as exc:
            retriever.retrieve("TSLA", "business")
        assert "8-dimensional" in str(exc.value)
        assert "EMBED_MODEL" in str(exc.value)
    finally:
        Settings.embed_model = old
