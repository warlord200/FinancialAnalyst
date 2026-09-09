export function NoCompanyPrompt({ onOpenIngest }: { onOpenIngest: () => void }) {
  return (
    <div className="card">
      <div className="empty-state">
        <div className="empty-copy" style={{ maxWidth: "none" }}>
          No company is open. Open one from the Portfolio to start its dossier.
        </div>
        <div className="empty-cta">
          <button onClick={onOpenIngest} className="btn btn-primary">
            Go to Portfolio
          </button>
        </div>
      </div>
    </div>
  );
}
