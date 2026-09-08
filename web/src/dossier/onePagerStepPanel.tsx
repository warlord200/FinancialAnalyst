import { useEffect } from "react";
import type { OnePagerResponse } from "../api";
import { NoCompanyPrompt } from "./noCompany";
import { OnePagerCard } from "./cards";

export function OnePagerStepPanel({
  ticker,
  onOpenIngest,
  response,
  loading,
  error,
  onLoad,
  onGate,
}: {
  ticker: string | null;
  onOpenIngest: () => void;
  response: OnePagerResponse | null;
  loading: boolean;
  error: string;
  onLoad: (symbol: string) => void;
  onGate: (decision: "accept" | "reject") => void;
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
          <span className="meta-text">Step 1 · one-pager · {ticker}</span>
          <button onClick={() => onLoad(ticker)} disabled={loading} className="primary">
            Analyze
          </button>
        </div>
        {loading && <div className="status">Loading one-pager…</div>}
        {error && <div className="error-banner">{error}</div>}
        {response && <OnePagerCard response={response} onGate={onGate} />}
      </main>
    </div>
  );
}
