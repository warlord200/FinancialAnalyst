# 10-K RAG Webapp — Design Spec

**Date:** 2026-08-07
**Status:** Approved (sections reviewed individually, pending final review)

## 1. Overview

A web application where a user types a stock ticker, the app auto-retrieves that company's most recent 10-K filings from SEC EDGAR, indexes them with the existing RAG pipeline, generates a structured financial analysis report, and displays it. Repeat requests for the same ticker return the stored report instantly (sticky cache) — no re-download, no re-index, no re-generation.

The app is built by **extending the existing FinancialAnalyst repo** (LlamaIndex + LiteParse + ChromaDB + DeepSeek), reusing `CustomDocs`, `LiteParseReader`, and the current data layout.

## 2. Goals / Non-goals

**Goals**
- Ticker → 10-K → stored analysis → rendered report, end-to-end.
- Sticky caching: a previously analyzed ticker returns instantly.
- Report covers current + prior fiscal year filings.
- Pre-generated report (no interactive chat).
- FastAPI backend + React frontend.

**Non-goals**
- Live chat / Q&A over the report.
- Auto-refresh on new SEC filings.
- Multi-user auth or multi-tenancy.
- Mobile-optimized design (responsive is nice-to-have only).

## 3. User Flow

1. User enters a ticker (e.g., `TSLA`) and clicks Analyze.
2. If ticker is already analyzed → report loads instantly.
3. Otherwise: app downloads current + prior-year 10-Ks from SEC EDGAR, indexes them, generates the report, saves it, and renders it.
4. User can view the report, browse history of analyzed tickers, and manually re-analyze a ticker.

## 4. Architecture

Six components:

### 4.1 SEC Downloader
`financial_analyst/ingestion/sec_downloader.py`
- Given a ticker, queries the SEC EDGAR company submissions API (`data.sec.gov/submissions/CIK<...>.json`, after resolving ticker → CIK via `files/company_tickers.json`) to discover filings.
- **EDGAR serves 10-Ks as HTML, not PDFs** (verified live: primary document `tsla-20251231.htm`, no PDF in filing index). The downloader downloads the **primary document HTML** for the two most recent 10-Ks to `data/<fiscal_year>/<TICKER>.htm` (e.g., `data/2026/TSLA.htm`, `data/2025/TSLA.htm`). Fiscal year is derived from `reportDate` (e.g., `2025-12-31` → `2025`).
- Respects EDGAR's 10 req/sec rate limit; sends a proper `User-Agent` header.
- Retries up to 3 times with backoff on rate-limit / network failures.
- The bundled `SECFilingsLoader` is **not used**: it requires the `unstructured` library (absent) and its section parser is unusable here.

### 4.1b SEC HTML Reader
`financial_analyst/reader/sec_html_reader.py` (a LlamaIndex `BaseReader`)
- Parses a downloaded `.htm` primary document (e.g., `tsla-20251231.htm`) — not LiteParse, which only accepts PDFs.
- Strips HTML tags (lxml is already installed) and splits the text by **SEC Item headings** (Item 1, 1A, 1B, 7, 8, …) using a regex like `(?i)item \d{1,3}(?:[a-z]|\([a-z]\))?`.
- Produces one `Document` per Item section, with metadata `{ticker, fiscal_year, item}`.
- This means report citations reference **Item sections** (e.g., "Item 1A") rather than page numbers.

### 4.2 Cache Registry
`financial_analyst/storage/registry.py`
- JSON store at `storage/registry.json`.
- Maps `TICKER → {fiscal_years: [...], report_path, report_generated_at}`.
- Provides add / get / clear operations and persistence round-trip.

### 4.3 Per-ticker index
- Reuses `CustomDocs` with light parameterization: collection and company name = ticker (e.g., `TSLA_vector_collection`, storage at `storage/TSLA`).
- **`CustomDocs` must accept a per-ticker file extractor** that maps `.htm → SECHtmlReader` (instead of only `.pdf → LiteParseReader`), and its page-label check must tolerate documents without `page_label` metadata.
- Loads from ChromaDB if already built; otherwise parses the downloaded `.htm` via `SECHtmlReader`.
- Both the vector index (facts/details) and summary index (high-level overview) are used.

### 4.4 Report Generator
`financial_analyst/analysis/report_generator.py`
- Runs a fixed set of query templates per filing year against the vector + summary indexes.
- Assembles a structured Markdown report.
- Asks the LLM to cite the **Item section** it drew from (metadata `item`, e.g., "Item 1A"), so citations appear inline like `(Item 1A)`. (EDGAR HTML has no page numbers; section-level citations are more meaningful for 10-Ks.)
- Computes the verdict label + score.

### 4.5 FastAPI backend
`api/main.py` + `api/services.py` (module-level singletons for embed model and LLM; heavy models loaded once at startup).

### 4.6 React frontend
`web/` (Vite + React).

## 5. Report Structure

Single Markdown report stored at `storage/<TICKER>/report.md`:

1. **Executive summary** — key takeaways + verdict.
   - **Verdict:** explicit label (`bullish` / `neutral` / `bearish`) + numeric score (0–100) + one-line rationale.
2. **Business overview** — what the company does, segments, customers, competition.
3. **Risk factors** — key risks from Item 1A, with page references.
4. **MD&A** — management's discussion: revenue drivers, margin trends, liquidity outlook.
5. **Segment performance** — per-segment revenue/profit for current and prior year.
6. **YoY trend comparison** — table of revenue, net income, EPS, operating margin, net margin, free cash flow with % change vs prior year.
7. **Financial health** — balance sheet highlights (debt, cash, working capital) and cash flow summary.
8. **Data provenance** — ticker, fiscal years, filing dates.

## 6. Request Lifecycle

**New ticker:**
`POST /api/analyze/TSLA` → registry miss → download current+prior 10-Ks → build/load CustomDocs index → report generator runs fixed queries → save `storage/TSLA/report.md` → registry entry written → return report.

**Repeat ticker:**
`POST /api/analyze/TSLA` → registry hit → return stored report immediately. No EDGAR call, no re-index.

## 7. API Surface

- `POST /api/analyze/{ticker}` → `{status: "cached"|"completed", report_path}`
- `GET /api/report/{ticker}` → `{ticker, fiscal_years, generated_at, verdict: {label, score, rationale}, markdown}`
- `GET /api/tickers` → `[{ticker, fiscal_years, generated_at}]` sorted by recency
- `POST /api/reanalyze/{ticker}` → clears cache entry + re-runs pipeline
- `GET /health`

Analysis runs synchronously (a fresh 2-filing analysis takes ~30–60s). Frontend shows progress/loading status.

CORS enabled for the dev frontend origin. Backend: `uvicorn`; frontend: `npm run dev` (separate processes).

## 8. Edge Cases & Error Handling

- **Invalid/delisted ticker:** EDGAR returns no filings → `404` with clear message; nothing cached; frontend error banner.
- **EDGAR rate limit / network failure:** retry up to 3 times with backoff, then surface "retry later". No partial cache entries written.
- **Missing second 10-K** (e.g., newly public company): proceed with single year; YoY shows "prior year unavailable"; scores use available filing; registry records the single year.
- **Concurrent requests for same ticker:** per-ticker in-process lock serializes; second caller waits then gets cached result. Different tickers run in parallel.
- **PDF parse failure / empty document:** raise; no report or registry entry written; error returned.
- **Sticky cache:** never auto-refreshed. Manual "Re-analyze" button deletes registry entry + report and re-runs pipeline.

## 9. Testing

- **Unit tests:**
  - SEC downloader — mocked EDGAR responses (requests patched): valid ticker, invalid ticker, missing second filing, rate-limit retry.
  - SEC HTML reader — fixture `.htm` with Item headings; asserts one Document per Item with `{ticker, fiscal_year, item}` metadata and no HTML tags.
  - Cache registry — add/get/clear, persistence round-trip, same-ticker locking.
  - Report generator — mocked index nodes; each section populated; verdict label + score present.
- **Integration test** (`tests/test_analyze_flow.py`): end-to-end with a small synthetic fixture `.htm` (2 filings) through download→index→report→registry; cached repeat call skips re-indexing.
- **API tests:** FastAPI `TestClient` with mocked services — cached vs completed, report shape, tickers list, 404 path.
- **Manual:** analyze a real ticker (e.g., TSLA) once; confirm second call is instant and report renders with verdict + YoY table.

Conventions: pytest (existing). Tests that hit DeepSeek/chromadb use lightweight fakes for speed and no network.

## 10. Tech Stack (confirmed)

- **Backend:** FastAPI, uvicorn, existing LlamaIndex RAG stack (LiteParse for existing PDFs, **custom `SECHtmlReader` for downloaded 10-Ks**, ChromaDB, DeepSeek, `Octen/Octen-Embedding-4B-INT8` embed model)
- **Frontend:** Vite + React, react-markdown for report rendering
- **Data:** SEC EDGAR (free), `data/` for raw downloaded `.htm` files, `storage/` for indexes + reports, `chroma_db/` for vectors
