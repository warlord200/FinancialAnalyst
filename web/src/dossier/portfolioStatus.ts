import type { PortfolioRow } from "../api";
import { DONE_STEPS, DOSSIER_STEPS, gateStatusChip } from "./steps";

export interface PortfolioStatusInfo {
  text: string;
  kind: string;
}

export const PORTFOLIO_STEPS = DOSSIER_STEPS.map((s) => s.n);

export function portfolioStatus(row: PortfolioRow): PortfolioStatusInfo {
  if (row.saved) return { text: "Saved to library", kind: "saved" };
  return gateStatusChip(row.gate.status === "pending" ? null : row.gate.status);
}

export function portfolioProgress(row: PortfolioRow): number {
  if (row.saved) return PORTFOLIO_STEPS.length;
  let count = row.gate.status === "accepted" ? 1 : 0;
  for (const n of DONE_STEPS) {
    if (row.done[String(n)]) count += 1;
  }
  return Math.min(Math.max(count, 0), PORTFOLIO_STEPS.length);
}
