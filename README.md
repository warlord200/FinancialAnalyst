# FinancialAnalyst , RAG Project

A **Retrieval-Augmented Generation (RAG)** pipeline built with [LlamaIndex](https://github.com/run-llama/llama_index) that enables an LLM agent to intelligently query and analyse financial documents. The agent supports both **vector search** and **summary-based retrieval**, with page-level metadata filtering and evaluated performance metrics.

---

## PROJECT STRUCTURE

| File | Purpose |
|---|---|
| `api/main.py` | FastAPI entrypoint wiring the ingestion/steps endpoints |
| `api/services.py` | Service singletons; builds the Cloudflare-hosted embed model |
| `financial_analyst/steps/retrieval.py` | Scoped hybrid retrieval + `CloudflareEmbedding` embedder |
| `financial_analyst/indexing/company_index.py` | Chroma collection lifecycle + embed-identity metadata |
| `financial_analyst/evaluation/eval_utils.py` | Monkey-patched evaluation utilities (see P4/S4 below) |
| `tests/test_llamaindex_agent.py` | Retrieval-quality eval harness (vector/hybrid/rerank) |

---

## KNOWLEDGE

This project was my deep-dive into building a production-ready RAG system. Beyond connecting an LLM to documents, I ran into several non-trivial problems around parsing, storage, metadata, evaluation correctness, and metric reliability. Each section below documents a real issue encountered and how it was resolved. This project also represents my current coding capabilities due to my minimized use of AI to solve problems (The RAG pipeline is implemented by hand while AI is used to generate the frontend/API).

---

## PROBLEMS AND SOLUTIONS

### P1 , LLM Tool Calling Fails with `SimpleDirectoryReader`

**Problem:** The LLM agent was unable to invoke tools because the tool layer could not correctly parse documents loaded via LlamaIndex's built-in `SimpleDirectoryReader`. The raw output wasn't structured in a way the tool pipeline could consume reliably.

**Solution:** Replaced `SimpleDirectoryReader` with a dedicated parser. [LlamaParse](https://github.com/run-llama/llama_parse) was the natural candidate but it is a paid service. Instead, **[LiteParse](https://github.com/iamarunbrahma/litparse)** was chosen , it is open-source, fast, and produced clean structured output that the tool layer could parse without errors.

---

### P2 , `SummaryIndex` Cannot Be Persisted to ChromaDB

**Problem:** After integrating ChromaDB as the vector store, `VectorStoreIndex` persisted correctly but `SummaryIndex` consistently failed.

**Root cause:** ChromaDB is designed exclusively to store **vector embeddings**. `SummaryIndex` operates on raw nodes , it does not produce embeddings and therefore has nothing ChromaDB can store.

**Solution:** Keep `VectorStoreIndex` backed by ChromaDB, and persist `SummaryIndex` using LlamaIndex's native `StorageContext` to a **separate local directory** (not the default `chroma_db` path). ChromaDB **auto-persists** to disk by default , calling `.persist()` manually is unnecessary.

```python
# SummaryIndex → separate StorageContext directory
storage_context_summary = StorageContext.from_defaults(persist_dir="./storage_summary")
```

---

### P3 , Metadata Filtering by Page Does Not Work

**Problem:** Page-level filtering returned incorrect or empty results even though documents were loaded successfully.

**Root cause:** LiteParse does **not** automatically inject `page_label` into node metadata. This must be **explicitly defined** during `load_data`.

**Solution:** Manually define the `load_data` method to inject page metadata, and add a helper that checks whether a collection already has `page_label` populated before filtering , preventing silent failures.

```python
doc.metadata["page_label"] = str(page_number)
```

---

### P4 , Evaluation Docs Are Outdated; Functions Were Removed

**Problem:** Much of the official LlamaIndex evaluation documentation references `llama-index-finetuning`, which was **deprecated in April 2026**. Functions like `generate_qa_embedding_pairs` and `evaluate_dataset` were either moved into `llama_index.core.eval` in an incomplete state or removed entirely without explanation.

**Solution:** Manually re-implemented the missing functions in `eval_utils.py`. Since the LlamaIndex source code cannot be modified directly, **monkey patching** was used to inject the corrected implementations at runtime.

```python
# eval_utils.py , monkey patching missing evaluate_dataset
import llama_index.core.evaluation as _eval

_eval.evaluate_dataset = custom_evaluate_dataset
```

---

### P5 , All Evaluation Metrics Return Zero

**Problem:** Every metric (faithfulness, relevancy, etc.) returned `0.0` regardless of query quality.

**Root cause:** Nodes used in `generate_qa_embedding_pairs` are **randomly initialised** by default. The evaluation function tracks nodes by identity, so runtime-generated nodes don't match the nodes used during retrieval , causing a complete mismatch that zeros out all scores.

**Solution:** Nodes must be **explicitly passed** every time `generate_qa_embedding_pairs` is called.

```python
qa_dataset = generate_qa_embedding_pairs(
    nodes=my_defined_nodes,  # ← must not be random/default
    llm=llm,
)
```

---

## TECH STACK

- **LlamaIndex** , RAG orchestration, agent, and index management
- **LiteParse** , Open-source document parser
- **ChromaDB** , Vector store for `VectorStoreIndex`
- **Qwen/Qwen3-Embedding-0.6B on Cloudflare Workers AI** , the single embed model (1024-dim), hosted — no local model is loaded for embedding
- **rank_bm25** , lexical BM25 leg of hybrid retrieval (fused by reciprocal rank)
- **bge-reranker-v2-m3** , optional cross-encoder reranker over fused candidates
- **Deepseek / LLM** , Language model backend

---

## NOTES

This project prioritises correctness and honest documentation of engineering challenges. `eval_utils.py` contains all monkey-patched workarounds with inline comments explaining why each exists. Issues with upstream libraries are noted with version references where applicable.

Retrieval is **hybrid by default** (`ScopedRetriever` in `financial_analyst/steps/retrieval.py`): a dense (embedding) leg and a BM25 keyword leg over the same scoped corpus are fused with reciprocal rank fusion (RRF). A cross-encoder reranker can be layered on top by setting `RERANKER_MODEL` (e.g. `BAAI/bge-reranker-v2-m3`); unset means no reranking. The measured effect of each stage is below.

## METRICS

Historical baselines (prior harness, embed model **Octen/Octen-Embedding-4B-INT8** on GPU, `top_k=4`):

```
19/7/2026 | MRR: 0.589 | HIT_RATE: 0.676
23/7/2026 | MRR: 0.767 | HIT_RATE: 0.851
```

Intermediate re-measurement (2/9/2026) with **BAAI/bge-small-en-v1.5** (CPU, same harness, same QA corpora) as the interim CPU-capable model while Octen was being replaced. Not directly comparable to the GPU baselines — weaker embed model.

| config | corpus | queries | MRR | hit_rate | ndcg |
|---|---|---|---|---|---|
| vector | Microsoft | 168 | 0.676 | 0.804 | 0.708 |
| hybrid | Microsoft | 168 | 0.725 | 0.899 | 0.769 |
| vector | Tesla | 163 | 0.713 | 0.840 | 0.745 |
| hybrid | Tesla | 163 | 0.785 | 0.914 | 0.818 |

Current measurement (4/9/2026) with the production embed model **Qwen/Qwen3-Embedding-0.6B served by Cloudflare Workers AI**, `top_k=4`. Same harness, same QA corpora. Embedding via Cloudflare produces vectors numerically identical to the local model (cosine 1.0000 checked on real AAPL chunks), so these are the Qwen3 numbers. Full corpora:

| config | corpus | queries | MRR | hit_rate | ndcg |
|---|---|---|---|---|---|
| vector | Microsoft | 168 | 0.785 | 0.917 | 0.819 |
| hybrid | Microsoft | 168 | 0.754 | 0.929 | 0.799 |
| vector | Tesla | 163 | 0.803 | 0.957 | 0.842 |
| hybrid | Tesla | 163 | 0.851 | 0.951 | 0.877 |

Aggregate over both corpora (weighted by query count): vector **0.794 MRR / 0.937 hit / 0.830 NDCG**; hybrid **0.802 MRR / 0.940 hit / 0.837 NDCG**.

Matched 40-query subset per corpus (seeded), hybrid vs reranked hybrid, same Qwen3/Cloudflare corpus:

| config | queries | MRR | hit_rate | ndcg |
|---|---|---|---|---|
| hybrid | 80 | 0.802 | 0.913 | 0.830 |
| hybrid + rerank | 80 | 0.856 | 0.913 | 0.871 |

**Query-prefix head-to-head (4/9/2026).** Qwen3 wants an `Instruct:...\nQuery:` prompt on queries; Cloudflare does not add it, so the embedder prepends it. Qwen's documented default ("Given a web search query…") was measured against a domain-tuned variant ("Given a question about a company's SEC filings…"). On the full 331-query corpora the documented default matched or beat the variant: vector **MRR 0.794 vs 0.786 / NDCG 0.830 vs 0.826**; hybrid **NDCG 0.837 vs 0.836** (hybrid MRR tied). On the smaller matched 80-query subset the variant edged ahead (hybrid MRR 0.822 vs 0.802; hybrid+rerank MRR 0.859 vs 0.856), but the full-corpus comparison is the larger, more reliable sample. **Decision: keep Qwen's documented default** as `EMBED_QUERY_INSTRUCTION`.

**Read on these numbers.** Moving from the interim bge-small to Qwen3/Cloudflare improves every config (vector MRR +0.08–0.12, hybrid +0.03–0.07), and the corpus re-ingest dropped from ~19–20 min of CPU embedding to ~1 min on the free Cloudflare tier. Hybrid (dense + BM25/RRF) still wins on Tesla (+0.048 MRR) and never loses on hit rate, but on Microsoft the dense-only leg now has the higher MRR/NDCG (0.785/0.819 vs 0.754/0.799) — the small aggregate edge for hybrid comes from Tesla. On the matched 80-query subset, adding the reranker on top of hybrid is again a clear gain: **+0.054 MRR, +0.041 NDCG**.

**Decision: hybrid stays the default** (it wins overall and on hit rate), with the Microsoft dense-vs-hybrid MRR inversion noted as a corpus-specific caveat. **The reranker stays behind `RERANKER_MODEL`** rather than forced on: it adds a ~2.3 GB cross-encoder and ~1 s/query on CPU. Embedding no longer holds a ~1.2 GB model resident (it is hosted), so a host that enables the reranker only needs memory for the reranker itself. (Latency note: hybrid adds a per-scope BM25 index that is built on the first query in that scope and cached thereafter — the search-everything scope is the whole corpus — plus a keyword pass per query; this has not been latency-profiled.) A standardised comparison method replacing this manual harness is the T13 eval's job.
