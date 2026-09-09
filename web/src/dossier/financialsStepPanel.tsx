import { useEffect } from "react";
import type { FinancialsResponse } from "../api";
import { NoCompanyPrompt } from "./noCompany";
import { FinancialsCard } from "./cards";
import { ChatPanel } from "./chat";
import { PeerScorecardPanel } from "./peers";
import { DoneMarkToggle } from "./doneMarkToggle";

export function FinancialsStepPanel({
  ticker,
  onOpenIngest,
  response,
  loading,
  error,
  onLoad,
  onQuotaChange,
  done,
  onToggleDone,
}: {
  ticker: string | null;
  onOpenIngest: () => void;
  response: FinancialsResponse | null;
  loading: boolean;
  error: string;
  onLoad: (symbol: string) => void;
  onQuotaChange: () => void;
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
          <h2>Financials</h2>
          <p className="step-scope">
            Step 3 of 6 · {ticker} · grounded in the 10-K Item 7 and Item 8 scope
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
          <span>Drafting Financials…</span>
        </div>
      )}
      {error && <div className="error-banner">{error}</div>}
      {response && <FinancialsCard response={response} />}
      {response && (
        <>
          <div className="panel-divider" />
          <PeerScorecardPanel ticker={ticker} onQuotaChange={onQuotaChange} />
          <div className="panel-divider" />
          <ChatPanel ticker={ticker} step={3} label="Financials" />
        </>
      )}
      <DoneMarkToggle done={done} opensLabel="open Step 4" onToggle={onToggleDone} />
    </div>
  );
}
