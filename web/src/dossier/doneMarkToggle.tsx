export function DoneMarkToggle({
  done,
  opensLabel,
  onToggle,
}: {
  done: boolean;
  opensLabel: string;
  onToggle: (done: boolean) => void;
}) {
  if (done) {
    return (
      <div className="done-mark done">
        <span className="badge badge-pass">Marked done</span>
        <span className="meta-text">Un-marking re-locks Steps 5-6.</span>
        <button type="button" className="link-button" onClick={() => onToggle(false)}>
          Un-mark done
        </button>
      </div>
    );
  }
  return (
    <div className="done-mark">
      <button type="button" className="primary" onClick={() => onToggle(true)}>
        Mark done — {opensLabel}
      </button>
      <span className="meta-text">Done marks are two-way: you can un-mark later.</span>
    </div>
  );
}
