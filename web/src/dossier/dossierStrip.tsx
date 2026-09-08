import type { StepGate } from "../api";
import {
  DOSSIER_STEPS,
  doneMapAll,
  stepIsDone,
  stepLockReason,
  type DossierStep,
} from "./steps";

function tabSub(
  step: DossierStep,
  gate: StepGate | null,
  done: Record<string, boolean>
): string {
  const reason = stepLockReason(step.n, gate, done);
  if (reason) {
    if (!gate) return "waiting on the gate";
    if (gate.status !== "accepted") {
      return step.n <= 4 ? "accept the one-pager first" : "accept, then mark 2-4 done";
    }
    return "mark Steps 2-4 done";
  }
  if (step.n === 1) {
    return gate?.status === "rejected" ? "rejected" : gate ? "decision made" : "gate decision";
  }
  if (step.n >= 5) return "open";
  return stepIsDone(step.n, gate, done) ? "done" : "in progress";
}

function tabClasses(
  step: DossierStep,
  gate: StepGate | null,
  done: Record<string, boolean>,
  active: boolean
): string {
  const classes = ["step-tab"];
  if (active) classes.push("active");
  if (stepLockReason(step.n, gate, done)) classes.push("locked");
  if (step.n === 1 && gate?.status === "rejected") classes.push("rejected");
  if (step.n > 1 && stepIsDone(step.n, gate, done)) classes.push("done");
  if (step.n === 1 && gate?.status === "accepted") classes.push("done");
  return classes.join(" ");
}

export function DossierStrip({
  gate,
  done,
  activeStep,
  onSelect,
}: {
  gate: StepGate | null;
  done: Record<string, boolean>;
  activeStep: number;
  onSelect: (n: number) => void;
}) {
  const accepted = gate?.status === "accepted";
  const allDone = accepted && doneMapAll(done);
  const badge = (n: number): string => {
    if (n === 1) return gate?.status === "rejected" ? "Rejected" : accepted ? "Accepted" : "Gate";
    if (n >= 5 && accepted && allDone) return "Open";
    if (n >= 2 && n <= 4 && accepted && done[String(n)]) return "Done";
    return "";
  };
  return (
    <div className="strip" role="tablist" aria-label="Dossier steps">
      {DOSSIER_STEPS.map((step) => {
        const locked = Boolean(stepLockReason(step.n, gate, done));
        const sub = tabSub(step, gate, done);
        const b = badge(step.n);
        return (
          <button
            key={step.n}
            type="button"
            role="tab"
            aria-selected={activeStep === step.n}
            title={locked ? `Step ${step.n} is locked. ${tabSub(step, gate, done)}` : undefined}
            className={tabClasses(step, gate, done, activeStep === step.n)}
            onClick={() => onSelect(step.n)}
          >
            <span className="step-head">
              <span className="step-num">Step {step.n}</span>
              {b && <span className="step-badge">{b}</span>}
            </span>
            <span className="step-name">{step.name}</span>
            <span className="step-sub">{sub}</span>
          </button>
        );
      })}
    </div>
  );
}

export function LockedStepNote({
  step,
  reason,
}: {
  step: DossierStep;
  reason: string;
}) {
  return (
    <div className="lock-note" role="status">
      <strong>
        Step {step.n} · {step.name} is locked.
      </strong>{" "}
      {reason}
    </div>
  );
}
