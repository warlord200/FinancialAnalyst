import type { LibraryRow } from "../api";
import { BookmarkIcon, ChevronRightIcon } from "./icons";

export function LibraryView({
  rows,
  loading,
  error,
  onOpen,
  onUnsave,
}: {
  rows: LibraryRow[];
  loading: boolean;
  error: string;
  onOpen: (ticker: string) => void;
  onUnsave: (ticker: string) => void;
}) {
  if (loading) {
    return (
      <div className="card">
        <div className="status">
          <span className="spinner" aria-hidden="true" />
          <span>Loading library…</span>
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
            <BookmarkIcon />
          </div>
          <div className="empty-title">Nothing saved yet.</div>
          <p className="empty-copy">
            Finish a dossier and choose Save to library at the end of Step 6.
            The saved company — with its read-only, source-tagged thesis —
            lives here.
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="card table-card">
      <div className="data-table-wrap">
        <table className="data-table library">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Saved on</th>
              <th className="row-chevron-col">
                <span className="sr-only">Open</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.ticker}
                className="data-row library-row"
                role="button"
                tabIndex={0}
                aria-label={`Open ${row.ticker}`}
                onClick={() => onOpen(row.ticker)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onOpen(row.ticker);
                  }
                }}
              >
                <td>
                  <strong className="ticker-cell">{row.ticker}</strong>
                </td>
                <td>
                  <span className="meta-text tabular">{row.saved_at.slice(0, 10)}</span>
                </td>
                <td className="row-chevron-cell">
                  <button
                    type="button"
                    className="unsave-btn"
                    aria-label={`Unsave ${row.ticker}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      onUnsave(row.ticker);
                    }}
                  >
                    Remove
                  </button>
                  <ChevronRightIcon size={17} className="row-chevron" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
