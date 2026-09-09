import { useEffect } from "react";
import type { BusinessSwotResponse } from "../api";
import { NoCompanyPrompt } from "./noCompany";
import { BusinessSwotCard } from "./cards";
import { ChatPanel } from "./chat";
import { DoneMarkToggle } from "./doneMarkToggle";

export function BusinessSwotStepPanel({
  ticker,
  onOpenIngest,
  response,
  loading,
  error,
  onLoad,
  done,
  onToggleDone,
}: {
  ticker: string | null;
  onOpenIngest: () => void;
  response: BusinessSwotResponse | null;
  loading: boolean;
  error: string;
  onLoad: (symbol: string) => void;
  done: boolean;
  onToggleDone: (done: boolean) => void;
}) {
  useEffect(() => {
    if (ticker && !response && !loading && !error) onLoad(ticker);
  }, [ticker, response, loading, error, onLoad]);

  if (!ticker) {
    return <NoCompanyPrompt onOpenIngest={onOpenIngest} />;
  }

  return (
    <div className="step-panel">
      <header className="step-panel-head">
        <div className="step-panel-title">
          <h2>Business &amp; SWOT</h2>
          <p className="step-scope">
            Step 2 of 6 · {ticker} · grounded in the 10-K Item 1 and Item 1A scope
          </p>
        </div>
        <div className="step-panel-actions">
          <button
            onClick={() => onLoad(ticker)}
            disabled={loading}
            className="btn btn-secondary btn-sm"
          >
            {loading ? "Drafting…" : response ? "Re-draft" : "Draft"}
          </button>
        </div>
      </header>
      {loading && (
        <div className="status">
          <span className="spinner" aria-hidden="true" />
          <span>Drafting Business &amp; SWOT…</span>
        </div>
      )}
      {error && <div className="error-banner">{error}</div>}
      {response && <BusinessSwotCard response={response} />}
      {response && (
        <>
          <div className="panel-divider" />
          <ChatPanel ticker={ticker} step={2} label="Business & SWOT" />
        </>
      )}
      <DoneMarkToggle done={done} opensLabel="open Step 3" onToggle={onToggleDone} />
    </div>
  );
}
