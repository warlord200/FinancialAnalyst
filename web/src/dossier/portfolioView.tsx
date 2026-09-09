import type { PortfolioRow } from "../api";
import { PORTFOLIO_STEPS, portfolioProgress, portfolioStatus } from "./portfolioStatus";
import { ChartIcon, ChevronRightIcon } from "./icons";

export function PortfolioView({
  rows,
  loading,
  error,
  onOpenCompany,
}: {
  rows: PortfolioRow[];
  loading: boolean;
  error: string;
  onOpenCompany: (ticker: string) => void;
}) {
  if (loading) {
    return (
      <div className="card">
        <div className="status">
          <span className="spinner" aria-hidden="true" />
          <span>Loading portfolio…</span>
        </div>
      </div>
    );
  }
  if (error) {
    return <div className="error-banner">{error}</div>;
  }
  if (rows.length === 0) {
    return (
      <div className="card">
        <div className="empty-state">
          <div className="empty-glyph" aria-hidden="true">
            <ChartIcon />
          </div>
          <div className="empty-title">Nothing ingested yet.</div>
          <p className="empty-copy">
            Enter a ticker above to pull its recent 10-K filings from SEC EDGAR.
            Once ingested, the company opens as a six-step dossier you can work
            through and save to your Library.
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="card table-card">
      <div className="data-table-wrap">
        <table className="data-table portfolio">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Dossier progress</th>
              <th>Status</th>
              <th className="row-chevron-col">
                <span className="sr-only">Open</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const progress = portfolioProgress(row);
              const status = portfolioStatus(row);
              return (
                <tr
                  key={row.ticker}
                  className="data-row portfolio-row"
                  role="button"
                  tabIndex={0}
                  aria-label={`Open ${row.ticker}`}
                  onClick={() => onOpenCompany(row.ticker)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onOpenCompany(row.ticker);
                    }
                  }}
                >
                  <td>
                    <strong className="ticker-cell">{row.ticker}</strong>
                  </td>
                  <td data-label="Dossier progress">
                    <span className="prog" aria-label={`Step ${progress} of 6 complete`}>
                      <span className="seg-track">
                        {PORTFOLIO_STEPS.map((_, i) => (
                          <span key={i} className={i < progress ? "pdot on" : "pdot"} />
                        ))}
                      </span>
                      <span className="prog-count">
                        {progress}/{PORTFOLIO_STEPS.length}
                      </span>
                    </span>
                  </td>
                  <td data-label="Status">
                    <span className={`status-chip status-${status.kind}`}>{status.text}</span>
                  </td>
                  <td className="row-chevron-cell">
                    <ChevronRightIcon size={17} className="row-chevron" />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
