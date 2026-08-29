from llama_index.core.schema import Document

from financial_analyst.reader.chunker import approx_tokens, chunk_documents


def test_chunk_documents_tags_metadata_and_splits_by_item():
    doc1 = Document(
        text="\n\n".join(f"Paragraph number {i} with several words to fill the chunk." for i in range(60)),
        metadata={"ticker": "TSLA", "fiscal_year": 2025, "item": "ITEM 7"},
    )
    doc2 = Document(
        text="A short standalone paragraph.",
        metadata={"ticker": "TSLA", "fiscal_year": 2024, "item": "ITEM 1"},
    )
    nodes = chunk_documents([doc1, doc2], chunk_size=40, chunk_overlap=5)

    assert len(nodes) >= 2
    item7 = [n for n in nodes if n.metadata["item"] == "ITEM 7"]
    item1 = [n for n in nodes if n.metadata["item"] == "ITEM 1"]

    assert len(item7) > 1
    assert len(item1) == 1
    assert item1[0].metadata["ticker"] == "TSLA"
    assert item1[0].metadata["fiscal_year"] == 2024
    assert item7[0].metadata["fiscal_year"] == 2025
    for n in nodes:
        assert approx_tokens(n.text) <= 45


def test_chunk_documents_does_not_mix_items():
    doc = Document(
        text="\n\n".join(f"Line {i} text content." for i in range(30)),
        metadata={"item": "ITEM 7"},
    )
    nodes = chunk_documents([doc], chunk_size=8, chunk_overlap=2)
    for n in nodes:
        assert n.metadata["item"] == "ITEM 7"


def test_chunk_documents_long_paragraph_split():
    doc = Document(
        text="word " * 200,
        metadata={"item": "ITEM 7"},
    )
    nodes = chunk_documents([doc], chunk_size=50, chunk_overlap=0)
    assert len(nodes) == 6
    assert all(approx_tokens(n.text) <= 50 for n in nodes)
