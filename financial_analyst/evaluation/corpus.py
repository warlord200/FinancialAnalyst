"""Reading a company's live indexed corpus into plain records.

The curated benchmark and the per-company smoke eval must see the same
chunks the production retriever queries — same chunking, same Item labels,
same fiscal years — not a re-embedded copy, or their per-step scoring
would describe a different corpus than the app serves. ``snapshot`` reads
a ``CompanyIndex`` collection (text plus the metadata the retriever filters
on) into a list of :class:`CorpusChunk` records; the collection is keyed by
ticker exactly like ``CompanyIndex.collection``, so a missing or empty
collection yields an empty list.
"""

from dataclasses import dataclass

import chromadb


@dataclass
class CorpusChunk:
    chunk_id: str
    text: str
    item: str | None = None
    fiscal_year: int | None = None
    filing: str | None = None


def snapshot(index, ticker: str) -> list[CorpusChunk]:
    """Every chunk of ``ticker``'s live collection as plain records."""
    ticker = ticker.upper()
    try:
        collection = index.collection(ticker)
    except chromadb.errors.NotFoundError:
        return []
    if collection.count() == 0:
        return []
    result = collection.get(include=["documents", "metadatas"])
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    ids = result.get("ids") or []
    chunks = []
    for chunk_id, doc, meta in zip(ids, documents, metadatas):
        meta = meta or {}
        chunks.append(
            CorpusChunk(
                chunk_id=str(chunk_id),
                text=doc,
                item=meta.get("item"),
                fiscal_year=meta.get("fiscal_year"),
                filing=meta.get("filing"),
            )
        )
    return chunks
