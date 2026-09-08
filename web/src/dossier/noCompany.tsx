export function NoCompanyPrompt({ onOpenIngest }: { onOpenIngest: () => void }) {
  return (
    <div className="search">
      <span className="meta-text">
        No company is open. Open one from the Portfolio to start its dossier.
      </span>
      <button onClick={onOpenIngest} className="primary">
        Go to Portfolio
      </button>
    </div>
  );
}
