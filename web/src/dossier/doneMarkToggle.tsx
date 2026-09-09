import { CheckIcon } from "./icons";

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
        <CheckIcon size={16} />
        <div className="done-mark-text">
          <strong>Marked done.</strong> You reviewed this step.
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={() => onToggle(false)}
        >
          Un-mark done
        </button>
      </div>
    );
  }
  return (
    <div className="done-mark">
      <div className="done-mark-text">
        Reviewed this step? Marking it done is two-way — you can un-mark any
        time.
      </div>
      <button type="button" className="btn btn-primary btn-sm" onClick={() => onToggle(true)}>
        Mark done — {opensLabel}
      </button>
    </div>
  );
}
