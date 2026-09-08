import type { LibraryRow } from "../api";

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
    return <div className="status">Loading library…</div>;
  }
  if (error) {
    return <div className="error-banner">{error}</div>;
  }
  if (rows.length === 0) {
    return (
      <p className="meta-text">
        Nothing saved yet — finish a dossier and Save to library at the end of
        Step 6.
      </p>
    );
  }
  return (
    <table className="library">
      <thead>
        <tr>
          <th>Ticker</th>
          <th>Saved on</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr
            key={row.ticker}
            className="library-row"
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
              <strong>{row.ticker}</strong>
            </td>
            <td>
              <span className="meta-text">{row.saved_at.slice(0, 10)}</span>
            </td>
            <td>
              <button
                type="button"
                className="link-button"
                aria-label={`Unsave ${row.ticker}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onUnsave(row.ticker);
                }}
              >
                Unsave
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
