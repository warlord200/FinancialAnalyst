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
  onToggleDone,
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
  onToggleDone: (symbol: string, step: number, done: boolean) => void;
  valDiscountPct: string;
  valGrowthPct: string;
  onDiscountChange: (value: string) => void;
  onGrowthChange: (value: string) => void;
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
          <span className="meta-text">Step 5 · Valuation · {ticker}</span>
          <button onClick={() => onLoad(ticker)} disabled={loading} className="primary">
            Analyze
          </button>
        </div>
        {loading && <div className="status">Loading valuation…</div>}
        {error && <div className="error-banner">{error}</div>}
        {response && (
          <ValuationPanel
            response={response}
            discountPct={valDiscountPct}
            growthPct={valGrowthPct}
            onDiscountChange={onDiscountChange}
            onGrowthChange={onGrowthChange}
            onToggleDone={(step, done) => onToggleDone(ticker, step, done)}
            onApplyAssumptions={() => onLoad(ticker)}
          />
        )}
      </main>
    </div>
  );
}
