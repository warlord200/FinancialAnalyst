import { useEffect } from "react";
import type { ThesisResponse } from "../api";
import { NoCompanyPrompt } from "./noCompany";
import { ThesisPanel } from "./thesis";

export function ThesisStepPanel({
  ticker,
  onOpenIngest,
  response,
  loading,
  error,
  onLoad,
  onToggleDone,
}: {
  ticker: string | null;
  onOpenIngest: () => void;
  response: ThesisResponse | null;
  loading: boolean;
  error: string;
  onLoad: (symbol: string) => void;
  onToggleDone: (symbol: string, step: number, done: boolean) => void;
}) {
  useEffect(() => {
    if (ticker && !response && !loading && !error) onLoad(ticker);
  }, [ticker, response, loading, error, onLoad]);

  if (!ticker) {
    return (
      <div className="layout">
        <main className="content">
          <NoCompanyPrompt onOpenIngest={onOpenIngest} />
        </main>
      </div>
    );
  }

  return (
    <div className="layout">
      <main className="content">
        <div className="search">
          <span className="meta-text">Step 6 · Thesis · {ticker}</span>
          <button onClick={() => onLoad(ticker)} disabled={loading} className="primary">
            Analyze
          </button>
        </div>
        {loading && <div className="status">Drafting thesis…</div>}
        {error && <div className="error-banner">{error}</div>}
        {response && (
          <ThesisPanel response={response} onToggleDone={(step, done) => onToggleDone(ticker, step, done)} />
        )}
      </main>
    </div>
  );
}
