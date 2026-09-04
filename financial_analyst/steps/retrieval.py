"""Scoped retrieval over a company's shared vector index.

The dossier steps draw on different parts of the corpus (step 2 uses
Item 1 / Item 1A, step 3 uses Items 7/8 and the numbers layer). This
module returns ``SourceChunk`` objects that carry the metadata needed to
source-tag an artifact section (Item, fiscal year, filing type).

There is exactly one embed model (``EMBED_MODEL``), used for both ingest
and query. It runs hosted on Cloudflare Workers AI (``CloudflareEmbedding``
in this module) rather than on the server, so no local model is loaded for
embedding. A collection is servable when the ``embed_model`` name recorded
on it at build time matches the server's current embed model; queries are
embedded with the query-side instruction (Qwen3 wants an ``Instruct:...``
prefix on queries, none on passages). A mismatched collection raises
``EmbedModelMismatchError`` telling the operator to re-ingest, so two
same-dimension models can never silently share a vector space.

Retrieval is hybrid by default: a dense (embedding) leg and a sparse
(BM25) leg over the same scoped corpus are fused with reciprocal rank
fusion, so keyword-exact matches that the vector search under-ranks can
still surface. An optional cross-encoder reranker (e.g.
``BAAI/bge-reranker-v2-m3``) can be layered on top of the fused
candidates; whether it helps on this corpus is measured by the eval
harness (``tests/test_llamaindex_agent.py``) and documented in README.
"""

import asyncio
import os
import re
import torch
from dataclasses import dataclass

import chromadb
from llama_index.core import Settings
from llama_index.core.embeddings import BaseEmbedding
from openai import OpenAI
from rank_bm25 import BM25Okapi

from financial_analyst.indexing.company_index import CompanyIndex

# Canonical model identity. The corpus records this name at build time and
# a collection is only servable by a model of the same name; it is the
# human-facing model, not the wire id used to call the hosting API.
EMBED_MODEL = "Qwen/Qwen3-Embedding-0.6B"
# Cloudflare Workers AI model id for the same model (Cloudflare hosts it
# under its own ``@cf/...`` slug). Vectors are interchangeable with the
# local model — see ADR-0001.
CLOUDFLARE_EMBED_MODEL = "@cf/qwen/qwen3-embedding-0.6b"
CLOUDFLARE_EMBEDDINGS_BASE_URL = (
    "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"
)
DEFAULT_RERANK_MODEL = "BAAI/bge-reranker-v2-m3"

# Qwen3 wants an ``Instruct: ...\nQuery: `` prefix on queries; passages
# are embedded with no instruction. The domain-tuned variant is measured
# head-to-head against Qwen's documented default in the eval harness
# (README "METRICS") before one is locked in.
EMBED_QUERY_INSTRUCTION = os.getenv(
    "EMBED_QUERY_INSTRUCTION",
    "Instruct: Given a web search query, retrieve relevant passages that "
    "answer the query\nQuery: ",
)

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


class CloudflareEmbedding(BaseEmbedding):
    """Hosted Qwen3 embedder backed by Cloudflare Workers AI.

    The same model the corpus is keyed on (``EMBED_MODEL``) runs on
    Cloudflare's side, so vectors are interchangeable with a locally
    embedded corpus and ``model_name`` keeps the canonical identity that
    ``CompanyIndex`` records at build time. Credentials are read from the
    environment (``CLOUDFLARE_ACCOUNT_ID`` / ``CLOUDFLARE_API_TOKEN``) and
    kept out of the model's serialized form.

    Cloudflare does not add Qwen3's query prompt, so ``query_instruction``
    is prepended to every query embedding and left off passages, matching
    the local embedder's behaviour.
    """

    def __init__(
        self,
        *,
        account_id: str,
        api_key: str,
        query_instruction: str = EMBED_QUERY_INSTRUCTION,
        model_name: str = EMBED_MODEL,
        embed_batch_size: int = 32,
        embeddings_cache=None,
    ) -> None:
        super().__init__(
            model_name=model_name,
            embed_batch_size=embed_batch_size,
            embeddings_cache=embeddings_cache,
        )
        object.__setattr__(self, "_account_id", account_id)
        object.__setattr__(self, "_api_key", api_key)
        object.__setattr__(self, "_query_instruction", query_instruction)
        object.__setattr__(self, "_client", None)

    def _ensure_client(self) -> OpenAI:
        if self._client is None:
            object.__setattr__(
                self,
                "_client",
                OpenAI(
                    api_key=self._api_key,
                    base_url=CLOUDFLARE_EMBEDDINGS_BASE_URL.format(
                        account_id=self._account_id
                    ),
                ),
            )
        return self._client

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._ensure_client().embeddings.create(
            model=CLOUDFLARE_EMBED_MODEL, input=texts
        )
        return [item.embedding for item in response.data]

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._embed([text])[0]

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._embed([self._query_instruction + query])[0]

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return await asyncio.to_thread(self._get_query_embedding, query)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return await asyncio.to_thread(self._get_text_embedding, text)

    async def _aget_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._get_text_embeddings, texts)


class EmbedModelMismatchError(Exception):
    """The collection's recorded embed model does not match the server's.

    Raised by name (a collection records the ``embed_model`` name it was
    built with; the server serves queries with its current model) or, for
    legacy corpora with no recorded name, by dimension.
    """

    def __init__(self, dim: int) -> None:
        if dim:
            head = f"The corpus was indexed with a {dim}-dimensional embedding model"
        else:
            head = "The corpus was indexed with an embedding model name"
        super().__init__(
            f"{head} that does not match the server's current embed model "
            "(EMBED_MODEL). Re-ingest the ticker with the current EMBED_MODEL "
            "setting to regenerate its vectors."
        )
        self.dim = dim


def tokenize(text: str) -> list[str]:
    """Split text into lowercased alphanumeric tokens for BM25."""
    return _TOKEN_RE.findall(text.lower())


def _chunk_key(chunk: "SourceChunk") -> tuple:
    """Identity of a chunk for cross-leg fusion: a chunk is the same
    document in both legs when its text and source metadata match."""
    return (chunk.text, chunk.item, chunk.fiscal_year, chunk.filing)


def reciprocal_rank_fusion(
    dense: list["SourceChunk"],
    sparse: list["SourceChunk"],
    k: int = 60,
) -> list["SourceChunk"]:
    """Fuse two ranked lists by reciprocal rank fusion.

    Each document scores ``sum(1 / (k + rank))`` across the legs it
    appears in. Docs seen by only one leg still participate, so a strong
    keyword match that the vector leg missed can rank in. Returns every
    fused document sorted by descending fused score (ties keep the dense
    order, which is deterministic for a given corpus and query).
    """
    by_key: dict[tuple, SourceChunk] = {}
    for chunk in [*dense, *sparse]:
        by_key.setdefault(_chunk_key(chunk), chunk)
    scores = {key: 0.0 for key in by_key}
    for leg in (dense, sparse):
        for rank, chunk in enumerate(leg, start=1):
            scores[_chunk_key(chunk)] += 1.0 / (k + rank)
    ordered = sorted(by_key, key=lambda key: scores[key], reverse=True)
    return [by_key[key] for key in ordered]


@dataclass
class SourceChunk:
    text: str
    item: str | None = None
    fiscal_year: int | None = None
    ticker: str = ""
    filing: str | None = None

    def to_dict(self) -> dict:
        """Serializable form of the chunk used for citations: the source
        metadata plus the passage text, so an answer can carry the chunks
        it came from."""
        return {
            "text": self.text,
            "item": self.item,
            "fiscal_year": self.fiscal_year,
            "ticker": self.ticker,
            "filing": self.filing,
        }


@dataclass
class _SparseIndex:
    bm25: BM25Okapi
    documents: list[str]
    metadatas: list[dict]


class CrossEncoderReranker:
    """Rerank candidate chunks with a cross-encoder.

    The model is loaded lazily on first use so constructing a retriever
    does not pull a multi-gigabyte model into memory. The default model
    (``BAAI/bge-reranker-v2-m3``) is a cached open-source reranker; the
    eval harness measures whether it helps on this financial corpus.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_RERANK_MODEL,
        device: str | None = None,
        max_length: int = 512,
    ) -> None:
        self.model_name = model_name
        self.device = device or str(
            torch.device("cuda" if torch.cuda.is_available() else "cpu")
        )
        self.max_length = max_length
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(
                self.model_name, device=self.device, max_length=self.max_length
            )
        return self._model

    def rerank(
        self,
        query: str,
        chunks: list[SourceChunk],
        top_n: int | None = None,
    ) -> list[SourceChunk]:
        if not chunks:
            return []
        model = self._ensure_model()
        pairs = [[query, chunk.text] for chunk in chunks]
        scores = model.predict(pairs, show_progress_bar=False)
        ordered = sorted(
            zip(chunks, scores), key=lambda pair: float(pair[1]), reverse=True
        )
        n = top_n if top_n is not None else len(ordered)
        return [chunk for chunk, _ in ordered[:n]]


def reranker_from_env() -> CrossEncoderReranker | None:
    """Build the production reranker from ``RERANKER_MODEL`` (empty disables)."""
    name = os.getenv("RERANKER_MODEL", "").strip()
    if not name:
        return None
    return CrossEncoderReranker(name)


class ScopedRetriever:
    def __init__(
        self,
        index: CompanyIndex,
        default_top_k: int = 4,
        use_hybrid: bool = True,
        reranker: CrossEncoderReranker | None = None,
        candidate_k: int | None = None,
        rrf_k: int = 60,
    ) -> None:
        self.index = index
        self.default_top_k = default_top_k
        self.use_hybrid = use_hybrid
        self.reranker = reranker
        self.candidate_k = candidate_k
        self.rrf_k = rrf_k
        self._settings_dim: int | None = None
        self._settings_probed = False
        self._sparse_cache: dict[tuple, _SparseIndex | None] = {}

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
            return len(model.get_query_embedding("probe"))
        except Exception:
            return None

    def _current_dim(self) -> int | None:
        if not self._settings_probed:
            self._settings_dim = self._probe_dim(Settings.embed_model)
            self._settings_probed = True
        return self._settings_dim

    def _resolve_query_model(self, collection):
        """Return the embed model that may query ``collection``.

        The server serves every query with the current embed model
        (``Settings.embed_model``). A collection is compatible when the
        ``embed_model`` name recorded on it at build time matches the
        current model — name, not dimension, is the identity signal, so
        two same-dimension models can never silently share a vector space.
        Legacy collections with no recorded name fall back to a dimension
        check, and any mismatch raises ``EmbedModelMismatchError`` telling
        the operator to re-ingest.
        """
        model = Settings.embed_model
        stored_dim = self._stored_dim(collection)
        recorded_name = (collection.metadata or {}).get("embed_model") or ""
        current_name = getattr(model, "model_name", "") or ""
        current_dim = self._current_dim()
        if recorded_name and current_name and recorded_name != current_name:
            raise EmbedModelMismatchError(stored_dim or 0)
        if current_dim is not None and stored_dim is not None and current_dim != stored_dim:
            raise EmbedModelMismatchError(stored_dim)
        return model

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

    @staticmethod
    def _chunk(text: str, meta: dict | None, ticker: str) -> SourceChunk:
        meta = meta or {}
        return SourceChunk(
            text=text,
            item=meta.get("item"),
            fiscal_year=meta.get("fiscal_year"),
            ticker=ticker,
            filing=meta.get("filing"),
        )

    def _query_dense(
        self,
        collection,
        query_embedding: list[float],
        where: dict | None,
        n: int,
        ticker: str,
    ) -> list[SourceChunk]:
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=n,
            where=where,
            include=["documents", "metadatas"],
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        return [self._chunk(doc, meta, ticker) for doc, meta in zip(documents, metadatas)]

    def _sparse_index(self, collection, where: dict | None) -> _SparseIndex | None:
        key = (collection.id, collection.count(), repr(where))
        if key in self._sparse_cache:
            return self._sparse_cache[key]
        if len(self._sparse_cache) > 64:
            self._sparse_cache.clear()
        result = collection.get(where=where, include=["documents", "metadatas"])
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        if not documents:
            index = None
        else:
            index = _SparseIndex(
                bm25=BM25Okapi([tokenize(doc) for doc in documents]),
                documents=documents,
                metadatas=metadatas or [],
            )
        self._sparse_cache[key] = index
        return index

    def _query_sparse(
        self,
        collection,
        query: str,
        where: dict | None,
        n: int,
        ticker: str,
    ) -> list[SourceChunk]:
        index = self._sparse_index(collection, where)
        if index is None:
            return []
        scores = index.bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        ranked = [i for i in ranked if scores[i] > 0][:n]
        return [
            self._chunk(index.documents[i], index.metadatas[i], ticker)
            for i in ranked
        ]

    def _candidate_pool(self, top_k: int) -> int:
        if self.candidate_k is not None:
            return self.candidate_k
        return max(top_k * 3, 12)

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
        if self._stored_dim(collection) is None:
            return []
        model = self._resolve_query_model(collection)
        query_embedding = model.get_query_embedding(query)
        k = top_k or self.default_top_k
        n = self._candidate_pool(k)
        where = self._where(items, fiscal_year)
        dense = self._query_dense(collection, query_embedding, where, n, ticker)
        if self.use_hybrid:
            sparse = self._query_sparse(collection, query, where, n, ticker)
            chunks = reciprocal_rank_fusion(dense, sparse, k=self.rrf_k)[:n]
        else:
            chunks = dense
        if self.reranker is not None and chunks:
            chunks = self.reranker.rerank(query, chunks, top_n=k)
        return chunks[:k]
