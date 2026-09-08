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
    return (
      <main className="content">
        <NoCompanyPrompt onOpenIngest={onOpenIngest} />
      </main>
    );
  }

  return (
    <main className="content">
      <div className="search">
        <span className="meta-text">Step 4 · Strategy · {ticker}</span>
        <button onClick={() => onLoad(ticker)} disabled={loading} className="primary">
          Analyze
        </button>
      </div>
      <DoneMarkToggle
        done={done}
        opensLabel="open Steps 5-6 (Valuation & Thesis)"
        onToggle={onToggleDone}
      />
      {loading && <div className="status">Drafting Strategy…</div>}
      {error && <div className="error-banner">{error}</div>}
      {response && <StrategyCard response={response} />}
      {response && <ChatPanel ticker={ticker} step={4} label="Strategy" />}
    </main>
  );
}
