import type { StepGate } from "../api";

export interface DossierStep {
  n: number;
  name: string;
}

export const DOSSIER_STEPS: DossierStep[] = [
  { n: 1, name: "One-pager" },
  { n: 2, name: "Business & SWOT" },
  { n: 3, name: "Financials" },
  { n: 4, name: "Strategy" },
  { n: 5, name: "Valuation" },
  { n: 6, name: "Thesis" },
];

export const DONE_STEPS = [2, 3, 4];

export type GateStatus = "accepted" | "rejected" | null;

export function gateStatus(gate: StepGate | null): GateStatus {
  return gate?.status ?? null;
}

export function doneMapAll(done: Record<string, boolean>): boolean {
  return DONE_STEPS.every((n) => Boolean(done[String(n)]));
}

export function stepIsDone(
  n: number,
  gate: StepGate | null,
  done: Record<string, boolean>
): boolean {
  if (n === 1) return gate?.status === "accepted";
  return Boolean(done[String(n)]);
}

/** Why step n cannot be opened, or null when it is open. */
export function stepLockReason(
  n: number,
  gate: StepGate | null,
  done: Record<string, boolean>
): string | null {
  if (n === 1) return null;
  const status = gateStatus(gate);
  const accepted = status === "accepted";
  if (!accepted) {
    const gateHint =
      status === "rejected"
        ? "Dossier is closed. Accept the Step 1 one-pager to reopen it."
        : "Opens once you accept the Step 1 one-pager.";
    if (n <= 4) return gateHint;
    return `${gateHint} Then mark Steps 2-4 done.`;
  }
  if (n >= 5) {
    const missing = DONE_STEPS.filter((step) => !done[String(step)]);
    const list = missing.map((step) => `Step ${step}`).join(", ");
    return `Opens once Steps 2-4 are all marked done. Missing: ${list}.`;
  }
  return null;
}
