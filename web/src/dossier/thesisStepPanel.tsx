import { useEffect } from "react";
import type { ThesisResponse } from "../api";
import { NoCompanyPrompt } from "./noCompany";
import { ThesisPanel } from "./thesis";
import { SaveToLibrary } from "./saveToLibrary";

export function ThesisStepPanel({
  ticker,
  onOpenIngest,
  response,
  loading,
  error,
  onLoad,
  saved,
  saveBusy,
  saveError,
  onSaveToLibrary,
  onUnsaveFromLibrary,
}: {
  ticker: string | null;
  onOpenIngest: () => void;
  response: ThesisResponse | null;
  loading: boolean;
  error: string;
  onLoad: (symbol: string) => void;
  saved: boolean;
  saveBusy: boolean;
  saveError: string;
  onSaveToLibrary: () => void;
  onUnsaveFromLibrary: () => void;
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
        <span className="meta-text">Step 6 · Thesis · {ticker}</span>
        <button onClick={() => onLoad(ticker)} disabled={loading} className="primary">
          Analyze
        </button>
      </div>
      {loading && <div className="status">Drafting thesis…</div>}
      {error && <div className="error-banner">{error}</div>}
      {response && <ThesisPanel response={response} />}
      {(saved || Boolean(response?.thesis)) && (
        <SaveToLibrary
          saved={saved}
          busy={saveBusy}
          error={saveError}
          onSave={onSaveToLibrary}
          onUnsave={onUnsaveFromLibrary}
        />
      )}
    </main>
  );
}
