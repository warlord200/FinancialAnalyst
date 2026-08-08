import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { analyzeTicker, getReport, listTickers, reanalyzeTicker, ReportData, TickerInfo } from "./api";

type Phase = "idle" | "loading" | "done" | "error";

export default function App() {
  const [ticker, setTicker] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [report, setReport] = useState<ReportData | null>(null);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<TickerInfo[]>([]);

  const refreshHistory = useCallback(() => {
    listTickers()
      .then(setHistory)
      .catch(() => setHistory([]));
  }, []);

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  async function run(tickerSymbol: string, redo = false) {
    const symbol = tickerSymbol.trim().toUpperCase();
    if (!symbol) return;
    setPhase("loading");
    setError("");
    setReport(null);
    try {
      if (redo) {
        await reanalyzeTicker(symbol);
      } else {
        await analyzeTicker(symbol);
      }
      const data = await getReport(symbol);
      setReport(data);
      setPhase("done");
      refreshHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
      setPhase("error");
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>10-K Financial Analyst</h1>
        <p>Type a ticker to analyze its latest 10-K filings.</p>
      </header>

      <div className="search">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run(ticker)}
          placeholder="e.g. TSLA"
          className="ticker-input"
        />
        <button onClick={() => run(ticker)} disabled={phase === "loading"} className="primary">
          Analyze
        </button>
      </div>

      {phase === "loading" && (
        <div className="status">
          <span className="spinner" aria-hidden="true" />
          Analyzing {ticker.toUpperCase()} — this takes ~30-60 seconds…
        </div>
      )}

      {phase === "error" && <div className="error-banner">{error}</div>}

      <div className="layout">
        <main className="content">
          {phase === "done" && report && (
            <article>
              <div className="report-meta">
                <span className={`verdict verdict-${report.verdict.label}`}>
                  {report.verdict.label.toUpperCase()} {report.verdict.score}/100
                </span>
                <span className="meta-text">
                  {report.fiscal_years.join(" / ")} · generated {report.generated_at.slice(0, 10)}
                </span>
                <button onClick={() => run(report.ticker, true)}>
                  Re-analyze
                </button>
              </div>
              <ReactMarkdown>{report.markdown}</ReactMarkdown>
            </article>
          )}
        </main>

        <aside className="sidebar">
          <h2>Analyzed tickers</h2>
          {history.length === 0 && <p>Nothing analyzed yet.</p>}
          <ul>
            {history.map((h) => (
              <li key={h.ticker}>
                <button onClick={() => run(h.ticker)} className="history-link">
                  {h.ticker}
                  {h.fiscal_years?.length ? ` (${h.fiscal_years.join("/")})` : ""}
                </button>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  );
}
