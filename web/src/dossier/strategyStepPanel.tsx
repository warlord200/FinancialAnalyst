import { useEffect } from "react";
import type { StrategyResponse } from "../api";
import { NoCompanyPrompt } from "./noCompany";
import { StrategyCard } from "./cards";
import { ChatPanel } from "./chat";
import { DoneMarkToggle } from "./doneMarkToggle";

export function StrategyStepPanel({
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
  response: StrategyResponse | null;
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
          <h2>Strategy</h2>
          <p className="step-scope">
            Step 4 of 6 · {ticker} · grounded in the 10-K Item 5 and Item 7 scope
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
          <span>Drafting Strategy…</span>
        </div>
      )}
      {error && <div className="error-banner">{error}</div>}
      {response && <StrategyCard response={response} />}
      {response && (
        <>
          <div className="panel-divider" />
          <ChatPanel ticker={ticker} step={4} label="Strategy" />
        </>
      )}
      <DoneMarkToggle
        done={done}
        opensLabel="open Steps 5-6 (Valuation & Thesis)"
        onToggle={onToggleDone}
      />
    </div>
  );
}
