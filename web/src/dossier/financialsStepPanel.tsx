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
    return (
      <main className="content">
        <NoCompanyPrompt onOpenIngest={onOpenIngest} />
      </main>
    );
  }

  return (
    <main className="content">
      <div className="search">
        <span className="meta-text">Step 3 · Financials · {ticker}</span>
        <button onClick={() => onLoad(ticker)} disabled={loading} className="primary">
          Analyze
        </button>
      </div>
      <DoneMarkToggle done={done} opensLabel="open Step 4" onToggle={onToggleDone} />
      {loading && <div className="status">Drafting Financials…</div>}
      {error && <div className="error-banner">{error}</div>}
      {response && <FinancialsCard response={response} />}
      {response && <PeerScorecardPanel ticker={ticker} onQuotaChange={onQuotaChange} />}
      {response && <ChatPanel ticker={ticker} step={3} label="Financials" />}
    </main>
  );
}
