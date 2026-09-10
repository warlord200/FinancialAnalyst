<div align="center">
  <img src="docs/brandmark.svg" alt="ThetaRadar" width="72" height="72" />
  <h1>ThetaRadar</h1>
  <p><em>Turn a company's own SEC filings into a source-grounded, six-step investment dossier.</em></p>
</div>

**ThetaRadar** ([thetaradar.me](https://thetaradar.me)) is a public web app for retail investors. You enter a US-listed ticker, it downloads the company's recent 10-K filings from SEC EDGAR, parses and indexes them, then walks a fixed six-step fundamental-analysis dossier — **One-pager → Business & SWOT → Financials → Strategy → Valuation → Thesis**. Every corpus-drafted claim carries page-level source tags. The retrieval engine is a hand-built hybrid RAG system whose quality is measured per configuration and published in [Metrics](#metrics).

> [!NOTE]
> The project ingests **10-K** filings today. The downloader scaffolds 10-Q counts, but quarterly ingestion is not yet enabled.

## Features

- **Six-step Coffin-method dossier** per ticker, ending in a thesis the user can save to their library.
- **Gated workflow** — nothing past Step 1 opens until the one-pager gate is accepted; Valuation and Thesis wait on the user's done-marks for Steps 2–4. Locked steps stay visible, never hidden.
- **Grounded drafting** — Steps 2–4 and 6 are drafted over a *scoped corpus* (Step 2 over Item 1/1A, Step 3 over Item 7/8, Step 4 over Item 5/7) and every section is validated against its sources before it is shown.
- **Hybrid retrieval** — dense (embedding) + BM25 keyword search fused by reciprocal-rank fusion, with an optional cross-encoder reranker.
- **Numbers layer** — XBRL statements parsed from EDGAR, with common-size tables, ratios, CAGR, and a price override.
- **Step-scoped chat** over the corpus for Steps 2–4, plus a "search everything" mode.
- **Accounts & quotas** — email + password, bearer tokens, verified/unverified tiers, and daily per-user limits on analyses and chat.
- **Durable ingestion** — a job-poller worker runs ingest jobs from a shared SQLite queue so they survive API restarts.

## How it works

```
SEC EDGAR ──▶ Downloader ──▶ Reader (Item sections) ──▶ Chunker ──▶ Embedder ──▶ Chroma
                                                                       │
   user query ──▶ ScopedRetriever ──▶ dense + BM25 ──▶ RRF ──▶ [reranker] ──▶ source-tagged chunks
```

**Ingestion.** `SECDownloader` pulls the latest filings; `SECHtmlReader` turns the primary HTML document into Item sections (splitting real sections from the table of contents and injecting page metadata); `chunk_documents` splits sections at paragraph boundaries; `CompanyIndex` embeds the nodes and writes a per-ticker Chroma collection, recording the embed-model identity used to build it.

**Retrieval.** `ScopedRetriever` queries one company's collection with metadata filters (Item, fiscal year). The dense leg runs on the hosted embed model and the sparse leg runs BM25 over the same scoped corpus; `reciprocal_rank_fusion` merges them. A cross-encoder reranker can be layered on top via `RERANKER_MODEL`. A collection is only servable by the embed model whose name matches the one recorded at build time, so two same-dimension models can never silently share a vector space — a mismatch tells the operator to re-ingest.

**Drafting.** `ArtifactGenerator` builds each dossier artifact from retrieved chunks and refuses to return a draft that fails source validation. See [`DESIGN.md`](DESIGN.md) for the full design language and [`docs/adr/`](docs/adr/) for decision records.

## Tech stack

| Layer | Choice |
|---|---|
| RAG orchestration | [LlamaIndex](https://github.com/run-llama/llama_index) |
| Vector store | [ChromaDB](https://www.trychroma.com/) |
| Embeddings | `Qwen/Qwen3-Embedding-0.6B` (1024-dim), hosted on [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/) — no local embed model is loaded |
| Lexical leg | `rank_bm25` (BM25) fused with dense results by RRF |
| Reranker (optional) | `BAAI/bge-reranker-v2-m3` cross-encoder |
| LLM | DeepSeek (`deepseek-v4-flash`) |
| Document parsing | Custom `SECHtmlReader` built on `lxml` (Item-section splitting + page metadata) |
| API | [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn |
| Frontend | React 18 + TypeScript + Vite |
| Auth & state | SQLite (users, quotas, step state, jobs) + JSON stores |
| Deployment | Caddy (HTTPS) + systemd on an Ubuntu VM |

## Getting started

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- A [DeepSeek API key](https://platform.deepseek.com/)
- A [Cloudflare account](https://dash.cloudflare.com/) with Workers AI enabled (`CLOUDFLARE_ACCOUNT_ID` and an API token)

### 1. Install

```bash
git clone https://github.com/warlord200/ThetaRadar.git
cd ThetaRadar

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

npm --prefix web ci
```

### 2. Configure

Create a `.env` file at the repo root (see [`deploy/.env.example`](deploy/.env.example)):

```dotenv
# LLM backend
DEEPSEEK_API_KEY=

# Embedding backend (Cloudflare Workers AI)
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_API_TOKEN=

# Ingest execution: "thread" for local dev, "worker" in production
JOB_RUNNER=thread

# Optional
# RERANKER_MODEL=BAAI/bge-reranker-v2-m3
# EMBED_BATCH_SIZE=32
# QUOTA_ANALYSES_VERIFIED=3
# QUOTA_ANALYSES_UNVERIFIED=1
# QUOTA_CHAT_VERIFIED=30
# QUOTA_CHAT_UNVERIFIED=10
```

### 3. Run

```bash
# Terminal 1 — API on http://localhost:8000
uvicorn api.main:app --reload

# Terminal 2 — web app on http://localhost:5173 (proxies /api to :8000)
npm --prefix web run dev
```

With `JOB_RUNNER=worker`, run the ingest worker in a third terminal:

```bash
python -m api.worker
```

> [!TIP]
> Open http://localhost:5173, sign up, then ingest a ticker (for example `MSFT`). Ingest jobs run in the background; the API exposes job status at `/api/ingest/jobs/{job_id}`.

## Testing

```bash
# Python — unit and API tests (offline; mocked embedders)
pytest

# Frontend — Vitest
npm --prefix web test
```

## Evaluation & metrics

The eval harness (`financial_analyst.evaluation.cli`) measures retrieval quality and writes the dashboard snapshot served at `/api/eval/summary`:

```bash
python -m financial_analyst.evaluation.cli curated              # hand-curated Tesla analyst benchmark
python -m financial_analyst.evaluation.cli regression           # synthetic sets vs. recorded baselines
python -m financial_analyst.evaluation.cli smoke --ticker AAPL  # per-company coverage + self-retrieval gate
```

The heavy modes need Cloudflare credentials and network access; the offline pytest suite covers every scoring path with mocked embedders. Regressions are reported when a metric falls more than `--tolerance` (default `0.02`) below its baseline.

### Metrics

Current measurement (4/9/2026) with the production embed model **Qwen/Qwen3-Embedding-0.6B on Cloudflare Workers AI**, `top_k=4`:

| config | corpus | queries | MRR | hit_rate | ndcg |
|---|---|---|---|---|---|
| vector | Microsoft | 168 | 0.785 | 0.917 | 0.819 |
| hybrid | Microsoft | 168 | 0.754 | 0.929 | 0.799 |
| vector | Tesla | 163 | 0.803 | 0.957 | 0.842 |
| hybrid | Tesla | 163 | 0.851 | 0.951 | 0.877 |

Aggregate over both corpora (weighted by query count): vector **0.794 MRR / 0.937 hit / 0.830 NDCG**; hybrid **0.802 MRR / 0.940 hit / 0.837 NDCG**.

Matched 40-query subset per corpus (seeded), hybrid vs. reranked hybrid:

| config | queries | MRR | hit_rate | ndcg |
|---|---|---|---|---|
| hybrid | 80 | 0.802 | 0.913 | 0.830 |
| hybrid + rerank | 80 | 0.856 | 0.913 | 0.871 |

**Read on these numbers.** Moving from the interim `bge-small-en-v1.5` to Qwen3/Cloudflare improved every config (vector MRR +0.08–0.12, hybrid +0.03–0.07), and corpus re-ingest dropped from ~19–20 min of CPU embedding to ~1 min on the free Cloudflare tier. Hybrid (dense + BM25/RRF) wins on Tesla (+0.048 MRR) and never loses on hit rate; on Microsoft the dense-only leg has the higher MRR/NDCG, so the small aggregate hybrid edge comes from Tesla. Adding the reranker on top of hybrid is a clear gain on the matched subset: **+0.054 MRR, +0.041 NDCG**.

**Decisions.** Hybrid stays the default (it wins overall and on hit rate). The reranker stays behind `RERANKER_MODEL` rather than forced on, because it adds a ~2.3 GB cross-encoder and ~1 s/query on CPU. Qwen's documented default query instruction is kept over a domain-tuned variant, which lost on the full 331-query corpora.

<details>
<summary>Earlier baselines (for continuity)</summary>

Historical baselines (prior harness, embed model **Octen/Octen-Embedding-4B-INT8** on GPU, `top_k=4`):

```
19/7/2026 | MRR: 0.589 | HIT_RATE: 0.676
23/7/2026 | MRR: 0.767 | HIT_RATE: 0.851
```

Interim re-measurement (2/9/2026) with **BAAI/bge-small-en-v1.5** (CPU, same harness and QA corpora), while Octen was being replaced:

| config | corpus | queries | MRR | hit_rate | ndcg |
|---|---|---|---|---|---|
| vector | Microsoft | 168 | 0.676 | 0.804 | 0.708 |
| hybrid | Microsoft | 168 | 0.725 | 0.899 | 0.769 |
| vector | Tesla | 163 | 0.713 | 0.840 | 0.745 |
| hybrid | Tesla | 163 | 0.785 | 0.914 | 0.818 |

</details>

## Deployment

The app runs on a single always-on server: FastAPI and the ingest worker as systemd units, the built React app served by Caddy with automatic HTTPS, and SQLite/Chroma on the persistent disk. The target is a free-tier Azure for Students VM (~1 GiB RAM, swap-enabled). See [`deploy/README.md`](deploy/README.md) for the full runbook.

```bash
# On the VM, with .env in place and JOB_RUNNER=worker
sudo DOMAIN=your-hostname ./deploy/setup.sh
```

## Project layout

| Path | Purpose |
|---|---|
| `api/` | FastAPI app (`main.py`), service singletons (`services.py`), ingest worker (`worker.py`) |
| `financial_analyst/ingestion/` | SEC EDGAR downloader and file reader |
| `financial_analyst/reader/` | HTML → Item sections (`sec_html_reader.py`), parsing, chunking |
| `financial_analyst/indexing/` | Chroma collection lifecycle and embed-identity metadata |
| `financial_analyst/steps/` | Retrieval, dossier step services, generation, chat, state |
| `financial_analyst/numbers/` | XBRL statements, prices, numbers service |
| `financial_analyst/auth/` | Users, tokens, sessions, quotas |
| `financial_analyst/evaluation/` | Eval harness: metrics, benchmarks, regression, smoke, CLI |
| `financial_analyst/storage/` | JSON and SQLite persistence helpers |
| `web/` | React + TypeScript frontend |
| `tests/` | Python test suite (mocked embedders, offline) |
| `deploy/` | Caddyfile, systemd units, provisioning script |
| `docs/adr/` | Architecture decision records |

## Engineering notes

A few non-obvious problems solved while building the pipeline — each is documented in code with inline comments:

- **Parsing for tool calls.** LlamaIndex's `SimpleDirectoryReader` produced output the tool layer could not consume reliably; `SECHtmlReader` replaced it, splitting filings into real Item sections (discarding the table-of-contents duplicates) and injecting page metadata explicitly.
- **Summary index persistence.** ChromaDB only stores vectors, so the `SummaryIndex` is persisted separately via LlamaIndex's native `StorageContext` rather than in the vector store.
- **Evaluation drift.** `llama-index-finetuning` was deprecated, so missing eval functions are re-implemented and monkey-patched in `eval_utils.py`; nodes must be passed explicitly to `generate_qa_embedding_pairs` or all metrics return zero.
- **Embed-model identity.** Corpus identity is keyed to the recorded model name, not the vector dimension, so changing the embed model forces a re-ingest ([ADR-0001](docs/adr/0001-single-embed-model-qwen3.md)).
