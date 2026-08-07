import chromadb
from llama_index.core.embeddings.mock_embed_model import MockEmbedding
from llama_index.core.llms import MockLLM
from llama_index.core import Settings

from financial_analyst.reader.sec_html_reader import SECHtmlReader


def test_custom_docs_with_html_extractor_builds_index(tmp_path):
    # Arrange: a tiny HTML "10-K" in a temp data dir
    data = tmp_path / "2025" / "TSLA.htm"
    data.parent.mkdir()
    data.write_text(
        "<html><body><h2>Item 1A.</h2><p>Competition risk.</p><h2>Item 7.</h2><p>Revenue grew.</p></body></html>",
        encoding="utf-8",
    )

    old_embed, old_llm = Settings._embed_model, Settings._llm
    Settings.embed_model = MockEmbedding(embed_dim=8)
    Settings.llm = MockLLM()
    try:
        from financial_analyst.indexing.CustomDocs import CustomDocs

        extractor = {".htm": SECHtmlReader()}
        cd = CustomDocs(
            "TSLA_2025",
            str(data),
            "Tesla 10-K fiscal 2025",
            extractor,
            chroma_path=str(tmp_path / "chroma"),
            storage_base=str(tmp_path / "storage"),
            requires_page_labels=False,
        )

        vec_idx, summ_idx = cd.get_indexes()
        resp = vec_idx.as_query_engine(similarity_top_k=2).query("What are the risks?")
        assert resp is not None
    finally:
        Settings._embed_model = old_embed
        Settings._llm = old_llm


def test_custom_docs_defaults_still_require_page_labels(tmp_path):
    # Verify default parameters did not change: constructor signature still exposes them
    import inspect

    from financial_analyst.indexing.CustomDocs import CustomDocs

    sig = inspect.signature(CustomDocs.__init__)
    assert sig.parameters["chroma_path"].default == "./chroma_db"
    assert sig.parameters["storage_base"].default == "./storage"
    assert sig.parameters["requires_page_labels"].default is True
