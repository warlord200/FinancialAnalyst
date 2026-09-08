import type { PortfolioRow } from "../api";
import { PORTFOLIO_STEPS, portfolioProgress, portfolioStatus } from "./portfolioStatus";

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
    return <div className="status">Loading portfolio…</div>;
  }
  if (error) {
    return <div className="error-banner">{error}</div>;
  }
  if (rows.length === 0) {
    return <p className="meta-text">Nothing ingested yet.</p>;
  }
  return (
    <table className="portfolio">
      <thead>
        <tr>
          <th>Ticker</th>
          <th>Dossier progress</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const progress = portfolioProgress(row);
          const status = portfolioStatus(row);
          return (
            <tr
              key={row.ticker}
              className="portfolio-row"
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
                <strong>{row.ticker}</strong>
              </td>
              <td>
                <span className="prog" aria-label={`Step ${progress} of 6 complete`}>
                  {PORTFOLIO_STEPS.map((_, i) => (
                    <span key={i} className={i < progress ? "pdot on" : "pdot"} />
                  ))}
                </span>
              </td>
              <td>
                <span className={`status-chip status-${status.kind}`}>{status.text}</span>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
