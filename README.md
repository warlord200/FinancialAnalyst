# 📊 FinancialAnalyst , RAG Project

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

This project was my deep-dive into building a production-ready RAG system. Beyond connecting an LLM to documents, I ran into several non-trivial problems around parsing, storage, metadata, evaluation correctness, and metric reliability. Each section below documents a real issue encountered and how it was resolved. This project also represents my current coding capabilities due to my minimized use of AI to solve problems (It is only used for code documentations).

---

## PROBLEMS AND SOLUTIONS

### P1 , LLM Tool Calling Fails with `SimpleDirectoryReader`

**Problem:** The LLM agent was unable to invoke tools because the tool layer could not correctly parse documents loaded via LlamaIndex's built-in `SimpleDirectoryReader`. The raw output wasn't structured in a way the tool pipeline could consume reliably.

**Solution:** Replaced `SimpleDirectoryReader` with a dedicated parser. [LlamaParse](https://github.com/run-llama/llama_parse) was the natural candidate but it is a paid service. Instead, **[LiteParse](https://github.com/iamarunbrahma/litparse)** was chosen , it is open-source, fast, and produced clean structured output that the tool layer could parse without errors.

> **Key takeaway:** Don't assume the default reader is always the right choice. For agentic tool use, the structure and cleanliness of parsed output matters as much as content.

---

### P2 , `SummaryIndex` Cannot Be Persisted to ChromaDB

**Problem:** After integrating ChromaDB as the vector store, `VectorStoreIndex` persisted correctly but `SummaryIndex` consistently failed.

**Root cause:** ChromaDB is designed exclusively to store **vector embeddings**. `SummaryIndex` operates on raw nodes , it does not produce embeddings and therefore has nothing ChromaDB can store.

**Solution:** Keep `VectorStoreIndex` backed by ChromaDB, and persist `SummaryIndex` using LlamaIndex's native `StorageContext` to a **separate local directory** (not the default `chroma_db` path). ChromaDB **auto-persists** to disk by default , calling `.persist()` manually is unnecessary.

```python
# SummaryIndex → separate StorageContext directory
storage_context_summary = StorageContext.from_defaults(persist_dir="./storage_summary")
```

> **Key takeaway:** Know your storage backend's constraints. ChromaDB = vectors only.

---

### P3 , Metadata Filtering by Page Does Not Work

**Problem:** Page-level filtering returned incorrect or empty results even though documents were loaded successfully.

**Root cause:** LiteParse does **not** automatically inject `page_label` into node metadata. This must be **explicitly defined** during `load_data`.

**Solution:** Manually define the `load_data` method to inject page metadata, and add a helper that checks whether a collection already has `page_label` populated before filtering , preventing silent failures.

```python
doc.metadata["page_label"] = str(page_number)
```

> **Key takeaway:** Always verify what metadata your nodes carry before relying on filters.

---

### P4 , Evaluation Docs Are Outdated; Functions Were Removed

**Problem:** Much of the official LlamaIndex evaluation documentation references `llama-index-finetuning`, which was **deprecated in April 2026**. Functions like `generate_qa_embedding_pairs` and `evaluate_dataset` were either moved into `llama_index.core.eval` in an incomplete state or removed entirely without explanation.

**Solution:** Manually re-implemented the missing functions in `eval_utils.py`. Since the LlamaIndex source code cannot be modified directly, **monkey patching** was used to inject the corrected implementations at runtime.

```python
# eval_utils.py , monkey patching missing evaluate_dataset
import llama_index.core.evaluation as _eval
_eval.evaluate_dataset = custom_evaluate_dataset
```

> **Key takeaway:** Pin your dependency versions. Be prepared to patch deprecated or missing functionality when working with rapidly evolving libraries.

---

### P5 , All Evaluation Metrics Return Zero

**Problem:** Every metric (faithfulness, relevancy, etc.) returned `0.0` regardless of query quality.

**Root cause:** Nodes used in `generate_qa_embedding_pairs` are **randomly initialised** by default. The evaluation function tracks nodes by identity, so runtime-generated nodes don't match the nodes used during retrieval , causing a complete mismatch that zeros out all scores.

**Solution:** Nodes must be **explicitly passed** every time `generate_qa_embedding_pairs` is called.

```python
qa_dataset = generate_qa_embedding_pairs(
    nodes=my_defined_nodes,   # ← must not be random/default
    llm=llm
)
```

> **Key takeaway:** Evaluation pipelines depend on node identity consistency. Randomised node initialisation silently breaks the entire eval loop.

---

## TECH STACK

- **LlamaIndex** , RAG orchestration, agent, and index management
- **LiteParse** , Open-source document parser
- **ChromaDB** , Vector store for `VectorStoreIndex`
- **Deepseek / LLM** , Language model backend

---

## NOTES

This project prioritises correctness and honest documentation of engineering challenges. `eval_utils.py` contains all monkey-patched workarounds with inline comments explaining why each exists. Issues with upstream libraries are noted with version references where applicable.

## METRICS
19/7/2026| MRR: 0.589 | HIT_RATE: 0.676