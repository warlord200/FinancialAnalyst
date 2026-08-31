"""Scoped retrieval over a company's shared vector index.

The dossier steps draw on different parts of the corpus (step 2 uses
Item 1 / Item 1A, step 3 uses Items 7/8 and the numbers layer). This
module returns ``SourceChunk`` objects that carry the metadata needed to
source-tag an artifact section (Item, fiscal year, filing type).
"""

from dataclasses import dataclass

import chromadb
from llama_index.core import VectorStoreIndex
from llama_index.core.vector_stores import (
    FilterCondition,
    MetadataFilter,
    MetadataFilters,
)
from llama_index.vector_stores.chroma import ChromaVectorStore

from financial_analyst.indexing.company_index import CompanyIndex


@dataclass
class SourceChunk:
    text: str
    item: str | None = None
    fiscal_year: int | None = None
    ticker: str = ""
    filing: str | None = None


class ScopedRetriever:
    def __init__(self, index: CompanyIndex, default_top_k: int = 4) -> None:
        self.index = index
        self.default_top_k = default_top_k

    def fiscal_years(self, ticker: str) -> list[int]:
        return self.index.stats(ticker.upper())["fiscal_years"]

    def retrieve(
        self,
        ticker: str,
        query: str,
        items: list[str] | None = None,
        fiscal_year: int | None = None,
        top_k: int | None = None,
    ) -> list[SourceChunk]:
        ticker = ticker.upper()
        try:
            collection = self.index.collection(ticker)
        except chromadb.errors.NotFoundError:
            return []
        store = ChromaVectorStore(chroma_collection=collection)
        index = VectorStoreIndex.from_vector_store(store)

        filters: list = []
        if items:
            filters.append(
                MetadataFilters(
                    filters=[MetadataFilter(key="item", value=item) for item in items],
                    condition=FilterCondition.OR,
                )
            )
        if fiscal_year is not None:
            filters.append(MetadataFilter(key="fiscal_year", value=fiscal_year))
        retriever = index.as_retriever(
            similarity_top_k=top_k or self.default_top_k,
            filters=MetadataFilters(filters=filters, condition=FilterCondition.AND)
            if filters
            else None,
        )
        nodes = retriever.retrieve(query)
        return [
            SourceChunk(
                text=node.node.get_content(),
                item=node.node.metadata.get("item"),
                fiscal_year=node.node.metadata.get("fiscal_year"),
                ticker=ticker,
                filing=node.node.metadata.get("filing"),
            )
            for node in nodes
        ]
