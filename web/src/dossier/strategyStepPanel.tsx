import { useEffect } from "react";
import type { StrategyResponse } from "../api";
import { NoCompanyPrompt } from "./noCompany";
import { StrategyCard } from "./cards";
import { ChatPanel } from "./chat";

export function StrategyStepPanel({
  ticker,
  onOpenIngest,
  response,
  loading,
  error,
  onLoad,
}: {
  ticker: string | null;
  onOpenIngest: () => void;
  response: StrategyResponse | null;
  loading: boolean;
  error: string;
  onLoad: (symbol: string) => void;
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
          <span className="meta-text">Step 4 · Strategy · {ticker}</span>
          <button onClick={() => onLoad(ticker)} disabled={loading} className="primary">
            Analyze
          </button>
        </div>
        {loading && <div className="status">Drafting Strategy…</div>}
        {error && <div className="error-banner">{error}</div>}
        {response && <StrategyCard response={response} />}
        {response && <ChatPanel ticker={ticker} step={4} label="Strategy" />}
      </main>
    </div>
  );
}
