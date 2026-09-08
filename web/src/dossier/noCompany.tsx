export function NoCompanyPrompt({ onOpenIngest }: { onOpenIngest: () => void }) {
  return (
    <div className="search">
      <span className="meta-text">
        No company is open. Open one from the Ingest list to start its dossier.
      </span>
      <button onClick={onOpenIngest} className="primary">
        Go to Ingest
      </button>
    </div>
  );
}
