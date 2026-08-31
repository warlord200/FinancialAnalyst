"""Scoped retrieval over a company's shared vector index.

The dossier steps draw on different parts of the corpus (step 2 uses
Item 1 / Item 1A, step 3 uses Items 7/8 and the numbers layer). This
module returns ``SourceChunk`` objects that carry the metadata needed to
source-tag an artifact section (Item, fiscal year, filing type).

Each company's vectors were embedded with whatever model was configured
when it was ingested, so queries are embedded with a model whose output
dimension matches the collection's stored vectors (recorded at build
time, or inferred from the stored vectors for legacy collections)
instead of assuming the process-global embed model matches.
"""

import torch
from dataclasses import dataclass

import chromadb
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from financial_analyst.indexing.company_index import CompanyIndex

DEFAULT_EMBED_MODEL = "BAAI/bge-m3"
HIGH_QUALITY_EMBED_MODEL = "Octen/Octen-Embedding-4B-INT8"
EMBED_MODEL_DIMS = {
    DEFAULT_EMBED_MODEL: 1024,
    HIGH_QUALITY_EMBED_MODEL: 2560,
}


class EmbedModelMismatchError(Exception):
    def __init__(self, dim: int) -> None:
        super().__init__(
            f"The corpus was indexed with a {dim}-dimensional embedding model that this "
            "server cannot load. Re-ingest the ticker with the current EMBED_MODEL setting "
            "to regenerate its vectors."
        )
        self.dim = dim


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
        self._models: dict[str, HuggingFaceEmbedding] = {}
        self._settings_dim: int | None = None
        self._settings_probed = False

    def fiscal_years(self, ticker: str) -> list[int]:
        return self.index.stats(ticker.upper())["fiscal_years"]

    def _stored_dim(self, collection) -> int | None:
        metadata = collection.metadata or {}
        if metadata.get("embed_dim"):
            return metadata["embed_dim"]
        sample = collection.get(limit=1, include=["embeddings"])
        embeddings = sample.get("embeddings")
        if embeddings is None or len(embeddings) == 0:
            return None
        return len(embeddings[0])

    def _probe_dim(self, model) -> int | None:
        try:
            return len(model.get_text_embedding("probe"))
        except Exception:
            return None

    def _current_dim(self) -> int | None:
        if not self._settings_probed:
            self._settings_dim = self._probe_dim(Settings.embed_model)
            self._settings_probed = True
        return self._settings_dim

    def _model_for_dim(self, dim: int):
        if self._current_dim() == dim and Settings.embed_model is not None:
            return Settings.embed_model
        name = next((n for n, d in EMBED_MODEL_DIMS.items() if d == dim), None)
        if name is None:
            raise EmbedModelMismatchError(dim)
        if name not in self._models:
            device = str(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
            model = HuggingFaceEmbedding(
                model_name=name, device=device, embed_batch_size=32
            )
            if self._probe_dim(model) != dim:
                raise EmbedModelMismatchError(dim)
            self._models[name] = model
        return self._models[name]

    @staticmethod
    def _where(items: list[str] | None, fiscal_year: int | None) -> dict | None:
        clauses = []
        if items:
            clauses.append({"item": {"$in": list(items)}})
        if fiscal_year is not None:
            clauses.append({"fiscal_year": fiscal_year})
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

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
        if collection.count() == 0:
            return []
        dim = self._stored_dim(collection)
        if dim is None:
            return []
        model = self._model_for_dim(dim)
        query_embedding = model.get_text_embedding(query)
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k or self.default_top_k,
            where=self._where(items, fiscal_year),
            include=["documents", "metadatas"],
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        chunks = []
        for text, meta in zip(documents, metadatas):
            meta = meta or {}
            chunks.append(
                SourceChunk(
                    text=text,
                    item=meta.get("item"),
                    fiscal_year=meta.get("fiscal_year"),
                    ticker=ticker,
                    filing=meta.get("filing"),
                )
            )
        return chunks
