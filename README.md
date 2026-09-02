# FinancialAnalyst , RAG Project

A **Retrieval-Augmented Generation (RAG)** pipeline built with [LlamaIndex](https://github.com/run-llama/llama_index) that enables an LLM agent to intelligently query and analyse financial documents. The agent supports both **vector search** and **summary-based retrieval**, with page-level metadata filtering and evaluated performance metrics.

---

## PROJECT STRUCTURE

| File | Purpose |
|---|---|
| `app.py` | Main entry point , sets up the agent and tools |
| `FileReader.py` | Document loading and parsing via LiteParse |
| `CustomDocs.py` | Custom document handling and metadata injection |
| `eval_utils.py` | Monkey-patched evaluation utilities (see P4/S4 below) |
| `helper.py` | Shared helper functions |
| `test_llamaindex_agent.py` | Agent integration tests |

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
- **rank_bm25** , lexical BM25 leg of hybrid retrieval (fused by reciprocal rank)
- **bge-reranker-v2-m3** , optional cross-encoder reranker over fused candidates
- **Deepseek / LLM** , Language model backend

---

## NOTES

This project prioritises correctness and honest documentation of engineering challenges. `eval_utils.py` contains all monkey-patched workarounds with inline comments explaining why each exists. Issues with upstream libraries are noted with version references where applicable.

Retrieval is **hybrid by default** (`ScopedRetriever` in `financial_analyst/steps/retrieval.py`): a dense (embedding) leg and a BM25 keyword leg over the same scoped corpus are fused with reciprocal rank fusion (RRF). A cross-encoder reranker can be layered on top by setting `RERANKER_MODEL` (e.g. `BAAI/bge-reranker-v2-m3`); unset means no reranking. The measured effect of each stage is below.

## METRICS

Historical baselines (prior harness, `tests/test_llamaindex_agent.py`, embed model **Octen/Octen-Embedding-4B-INT8** on GPU, `top_k=4`):

```
19/7/2026 | MRR: 0.589 | HIT_RATE: 0.676
23/7/2026 | MRR: 0.767 | HIT_RATE: 0.851
```

Re-measurement for hybrid + reranker (2/9/2026). The QA datasets in `storage/evals/` are re-embedded with the configured embed model so everything runs on CPU; the Octen model needs a GPU, and this dev box only has fully-cached CPU models, so the run below uses **BAAI/bge-small-en-v1.5** with `top_k=4`. Same harness, same datasets, all configs measured side by side. Two caveats make these **not directly comparable** to the GPU baselines above: the embed model differs (bge-small-en-v1.5 is weaker than Octen), and the corpus is the QA-dataset chunks only, so the numbers sit on a smaller search space than the old harness measured.

| config | corpus | queries | MRR | hit_rate | ndcg |
|---|---|---|---|---|---|
| vector | Microsoft | 168 | 0.676 | 0.804 | 0.708 |
| hybrid | Microsoft | 168 | 0.725 | 0.899 | 0.769 |
| vector | Tesla | 163 | 0.713 | 0.840 | 0.745 |
| hybrid | Tesla | 163 | 0.785 | 0.914 | 0.818 |

Matched 40-query subset per corpus (seeded), hybrid vs reranked hybrid:

| config | queries | MRR | hit_rate | ndcg |
|---|---|---|---|---|
| hybrid | 80 | 0.792 | 0.888 | 0.816 |
| hybrid + rerank | 80 | 0.856 | 0.913 | 0.871 |

**Read on these numbers.** On the full 331-query corpora, hybrid (dense + BM25/RRF) is a clear, consistent win over pure vector search: **+0.05–0.07 MRR, +0.07–0.10 hit rate, +0.06–0.07 NDCG** on both companies, so hybrid is the production retrieval path. On the matched 80-query subset, adding the cached open-source reranker (`BAAI/bge-reranker-v2-m3`) on top of hybrid is a further, smaller gain over hybrid on that same subset: **+0.065 MRR, +0.025 hit rate, +0.055 NDCG**. That the reranker helps at all contradicts the earlier assumption (comment in the old eval script, 23/7) that open-source rerankers are not usable on financial data.

**Decision: keep both.** Hybrid is on by default. The reranker is kept behind `RERANKER_MODEL` rather than forced on: it adds a ~2.3 GB cross-encoder and ~1 s/query on CPU, which strains the 2–4 GB student-hosting budget in `docs/research/student-hosting-options-2026.md`; enable it when latency/RAM allow. (Latency note: hybrid itself adds a per-scope BM25 index that is built on the first query in that scope and cached thereafter — the search-everything scope is the whole corpus — plus a keyword pass per query; this has not been latency-profiled.) A fuller run on the production embed model (bge-m3 or Octen on GPU) and a standardised comparison method is the T13 eval harness's job.
