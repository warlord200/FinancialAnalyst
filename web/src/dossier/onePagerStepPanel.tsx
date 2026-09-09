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
    return <NoCompanyPrompt onOpenIngest={onOpenIngest} />;
  }

  return (
    <div className="step-panel">
      <header className="step-panel-head">
        <div className="step-panel-title">
          <h2>One-pager</h2>
          <p className="step-scope">
            Step 1 of 6 · {ticker} · a snapshot drawn from the parsed XBRL numbers
          </p>
        </div>
        <div className="step-panel-actions">
          <button onClick={() => onLoad(ticker)} disabled={loading} className="btn btn-primary btn-sm">
            {loading ? "Analyzing…" : "Analyze"}
          </button>
        </div>
      </header>
      {loading && (
        <div className="status">
          <span className="spinner" aria-hidden="true" />
          <span>Loading one-pager…</span>
        </div>
      )}
      {error && <div className="error-banner">{error}</div>}
      {response && <OnePagerCard response={response} onGate={onGate} />}
    </div>
  );
}
