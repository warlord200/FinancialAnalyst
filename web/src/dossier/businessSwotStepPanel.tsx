import { useEffect } from "react";
import type { BusinessSwotResponse } from "../api";
import { NoCompanyPrompt } from "./noCompany";
import { BusinessSwotCard } from "./cards";
import { ChatPanel } from "./chat";

export function BusinessSwotStepPanel({
  ticker,
  onOpenIngest,
  response,
  loading,
  error,
  onLoad,
}: {
  ticker: string | null;
  onOpenIngest: () => void;
  response: BusinessSwotResponse | null;
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
          <span className="meta-text">Step 2 · Business & SWOT · {ticker}</span>
          <button onClick={() => onLoad(ticker)} disabled={loading} className="primary">
            Analyze
          </button>
        </div>
        {loading && <div className="status">Drafting Business & SWOT…</div>}
        {error && <div className="error-banner">{error}</div>}
        {response && <BusinessSwotCard response={response} />}
        {response && <ChatPanel ticker={ticker} step={2} label="Business & SWOT" />}
      </main>
    </div>
  );
}
