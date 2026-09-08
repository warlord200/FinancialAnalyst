export function SaveToLibrary({
  saved,
  busy,
  error,
  onSave,
  onUnsave,
}: {
  saved: boolean;
  busy: boolean;
  error: string;
  onSave: () => void;
  onUnsave: () => void;
}) {
  return (
    <>
      {saved ? (
        <div className="save-to-library">
          <span className="saved-badge">✓ Saved to library</span>
          <button type="button" className="link-button" disabled={busy} onClick={onUnsave}>
            Unsave
          </button>
        </div>
      ) : (
        <div className="save-to-library">
          <button type="button" className="primary" disabled={busy} onClick={onSave}>
            Save to library
          </button>
          <span className="meta-text">
            Read-only, source-tagged thesis. Saving moves the completed company into your Library.
          </span>
        </div>
      )}
      {error ? <div className="error-banner">{error}</div> : null}
    </>
  );
}
