import re

from llama_index.core.schema import Document, TextNode


def approx_tokens(text: str) -> int:
    return max(1, round(len(text.split()) * 1.3))


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _split_long_paragraph(paragraph: str, chunk_size: int) -> list[str]:
    word_window = max(1, int(chunk_size / 1.3))
    words = paragraph.split()
    return [
        " ".join(words[i : i + word_window])
        for i in range(0, len(words), word_window)
    ]


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    paragraphs = _split_paragraphs(text)
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    for para in paragraphs:
        if approx_tokens(para) > chunk_size:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_words = 0
            for piece in _split_long_paragraph(para, chunk_size):
                chunks.append(piece)
            continue

        if current and current_words + approx_tokens(para) > chunk_size:
            carry: list[str] = []
            carry_words = 0
            for prev in reversed(current):
                words = approx_tokens(prev)
                if carry_words + words > max(0, chunk_overlap):
                    break
                carry.insert(0, prev)
                carry_words += words
            chunks.append("\n\n".join(current))
            current = carry
            current_words = carry_words

        current.append(para)
        current_words += approx_tokens(para)

    if current:
        chunks.append("\n\n".join(current))

    return [c for c in chunks if c.strip()]


def chunk_documents(
    documents: list[Document],
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> list[TextNode]:
    nodes: list[TextNode] = []
    for doc in documents:
        for text in _chunk_text(doc.text, chunk_size, chunk_overlap):
            nodes.append(TextNode(text=text, metadata=dict(doc.metadata)))
    return nodes
