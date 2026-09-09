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
    return <NoCompanyPrompt onOpenIngest={onOpenIngest} />;
  }

  return (
    <div className="step-panel">
      <header className="step-panel-head">
        <div className="step-panel-title">
          <h2>Thesis</h2>
          <p className="step-scope">
            Step 6 of 6 · {ticker} · the whole dossier, drawn into an
            investment view you can save to your Library
          </p>
        </div>
        <div className="step-panel-actions">
          <button
            onClick={() => onLoad(ticker)}
            disabled={loading}
            className="btn btn-secondary btn-sm"
          >
            {loading ? "Drafting…" : "Re-draft"}
          </button>
        </div>
      </header>
      {loading && (
        <div className="status">
          <span className="spinner" aria-hidden="true" />
          <span>Drafting thesis…</span>
        </div>
      )}
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
    </div>
  );
}
