import { useEffect } from "react";
import type { ValuationResponse } from "../api";
import { NoCompanyPrompt } from "./noCompany";
import { ValuationPanel } from "./valuation";

export function ValuationStepPanel({
  ticker,
  onOpenIngest,
  response,
  loading,
  error,
  onLoad,
  valDiscountPct,
  valGrowthPct,
  onDiscountChange,
  onGrowthChange,
}: {
  ticker: string | null;
  onOpenIngest: () => void;
  response: ValuationResponse | null;
  loading: boolean;
  error: string;
  onLoad: (symbol: string) => void;
  valDiscountPct: string;
  valGrowthPct: string;
  onDiscountChange: (value: string) => void;
  onGrowthChange: (value: string) => void;
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
          <h2>Valuation</h2>
          <p className="step-scope">
            Step 5 of 6 · {ticker} · DCF and current multiples, derived from the
            numbers layer
          </p>
        </div>
        <div className="step-panel-actions">
          <button
            onClick={() => onLoad(ticker)}
            disabled={loading}
            className="btn btn-secondary btn-sm"
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>
      </header>
      {loading && (
        <div className="status">
          <span className="spinner" aria-hidden="true" />
          <span>Loading valuation…</span>
        </div>
      )}
      {error && <div className="error-banner">{error}</div>}
      {response && (
        <ValuationPanel
          response={response}
          discountPct={valDiscountPct}
          growthPct={valGrowthPct}
          onDiscountChange={onDiscountChange}
          onGrowthChange={onGrowthChange}
          onApplyAssumptions={() => onLoad(ticker)}
        />
      )}
    </div>
  );
}
