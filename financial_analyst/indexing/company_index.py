from collections import Counter

import chromadb
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.vector_stores.chroma import ChromaVectorStore


class CompanyIndex:
    def __init__(
        self, chroma_path: str = "./chroma_db", storage_base: str = "./storage"
    ) -> None:
        self.chroma_path = chroma_path
        self.storage_base = storage_base

    def _client(self) -> chromadb.ClientAPI:
        return chromadb.PersistentClient(path=self.chroma_path)

    def collection_name(self, ticker: str) -> str:
        return f"{ticker.upper()}_vector_collection"

    def collection(self, ticker: str):
        return self._client().get_collection(self.collection_name(ticker))

    def build(self, ticker: str, nodes: list[TextNode]) -> int:
        db = self._client()
        name = self.collection_name(ticker)
        try:
            db.delete_collection(name)
        except Exception:
            pass
        collection = db.create_collection(name)
        store = ChromaVectorStore(chroma_collection=collection)
        context = StorageContext.from_defaults(vector_store=store)
        VectorStoreIndex(nodes=nodes, storage_context=context)
        return collection.count()

    def stats(self, ticker: str) -> dict:
        try:
            collection = self._client().get_collection(self.collection_name(ticker))
        except Exception:
            return {
                "num_chunks": 0,
                "chunks_by_item": {},
                "chunks_by_year": {},
                "fiscal_years": [],
            }
        count = collection.count()
        metadatas = collection.get(limit=count, include=["metadatas"])["metadatas"] or []
        by_item: Counter = Counter()
        by_year: Counter = Counter()
        years: set = set()
        for m in metadatas:
            item = m.get("item")
            fiscal_year = m.get("fiscal_year")
            if item:
                by_item[item] += 1
            if fiscal_year is not None:
                by_year[str(fiscal_year)] += 1
                years.add(fiscal_year)
        return {
            "num_chunks": count,
            "chunks_by_item": dict(by_item),
            "chunks_by_year": dict(by_year),
            "fiscal_years": sorted(years, reverse=True),
        }
