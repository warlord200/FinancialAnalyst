import { useCallback, useEffect, useState } from "react";
import {
  getIngestJob,
  getIngestStats,
  ingestTicker,
  listIngested,
  IngestJob,
  IngestedTicker,
  IngestStats,
} from "./api";

type Phase = "idle" | "ingesting" | "done" | "error";

function ChunkTable({ title, rows }: { title: string; rows: [string, number][] }) {
  return (
    <>
      <h2>{title}</h2>
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Chunks</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, count]) => (
            <tr key={label}>
              <td>{label}</td>
              <td>{count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

export default function App() {
  const [ticker, setTicker] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [job, setJob] = useState<IngestJob | null>(null);
  const [stats, setStats] = useState<IngestStats | null>(null);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<IngestedTicker[]>([]);

  const refreshHistory = useCallback(() => {
    listIngested()
      .then(setHistory)
      .catch(() => setHistory([]));
  }, []);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  async function openStats(symbol: string) {
    const data = await getIngestStats(symbol);
    setStats(data);
    setPhase("done");
  }

  async function run(symbol: string) {
    const s = symbol.trim().toUpperCase();
    if (!s) return;
    setPhase("ingesting");
    setError("");
    setStats(null);
    setJob(null);
    try {
      const res = await ingestTicker(s);
      if (res.status === "cached") {
        await openStats(s);
        refreshHistory();
        return;
      }
      const jobId = res.job_id ?? "";
      while (true) {
        const current = await getIngestJob(jobId);
        setJob(current);
        if (current.status === "completed") {
          await openStats(s);
          refreshHistory();
          return;
        }
        if (current.status === "failed") {
          setError(current.error || "Ingestion failed");
          setPhase("error");
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ingestion failed");
      setPhase("error");
    }
  }

  const byItemRows = stats ? Object.entries(stats.chunks_by_item).sort() : [];
  const byYearRows = stats ? Object.entries(stats.chunks_by_year).sort() : [];

  return (
    <div className="app">
      <header className="header">
        <h1>Financial Analyst</h1>
        <p>Type a ticker to ingest its 10-K and 10-Q filings.</p>
      </header>

      <div className="search">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run(ticker)}
          placeholder="e.g. TSLA"
          className="ticker-input"
        />
        <button
          onClick={() => run(ticker)}
          disabled={phase === "ingesting"}
          className="primary"
        >
          Ingest
        </button>
      </div>

      {phase === "ingesting" && (
        <div className="status">
          <span className="spinner" aria-hidden="true" />
          {job
            ? `Ingesting ${job.ticker} — ${job.status} (${job.progress}%)`
            : `Ingesting ${ticker.toUpperCase()} — starting job…`}
          <progress value={job?.progress ?? 0} max={100} style={{ display: "block", width: "100%", marginTop: 8 }} />
        </div>
      )}

      {phase === "error" && <div className="error-banner">{error}</div>}

      <div className="layout">
        <main className="content">
          {phase === "done" && stats && (
            <article>
              <div className="report-meta">
                <span className="meta-text">
                  {stats.ticker} · ingested {stats.ingested_at.slice(0, 10)} ·{" "}
                  {stats.num_chunks} chunks · fiscal years{" "}
                  {stats.fiscal_years.join(", ")}
                </span>
              </div>
              <ChunkTable title="Chunks by Item" rows={byItemRows} />
              <ChunkTable title="Chunks by Fiscal Year" rows={byYearRows} />
            </article>
          )}
        </main>

        <aside className="sidebar">
          <h2>Ingested tickers</h2>
          {history.length === 0 && <p>Nothing ingested yet.</p>}
          <ul>
            {history.map((h) => (
              <li key={h.ticker}>
                <button
                  onClick={() => openStats(h.ticker)}
                  className="history-link"
                >
                  {h.ticker}
                  {h.fiscal_years?.length
                    ? ` (${h.fiscal_years.join("/")})`
                    : ""}
                </button>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  );
}
