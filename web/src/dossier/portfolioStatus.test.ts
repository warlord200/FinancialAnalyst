import { describe, it, expect } from "vitest";
import type { PortfolioRow } from "../api";
import { PORTFOLIO_STEPS, portfolioProgress, portfolioStatus } from "./portfolioStatus";

const row = (over: Partial<PortfolioRow>): PortfolioRow => ({
  ticker: "TSLA",
  ingested_at: null,
  numbers_ready: false,
  gate: { status: "pending" },
  done: {},
  saved: false,
  ...over,
});

describe("portfolioStatus", () => {
  it("maps a fresh company to a pending gate chip", () => {
    expect(portfolioStatus(row({ gate: { status: "pending" } }))).toEqual({
      text: "Gate pending",
      kind: "pending",
    });
  });

  it("maps a rejected company to a rejected chip", () => {
    expect(portfolioStatus(row({ gate: { status: "rejected" } }))).toEqual({
      text: "Rejected",
      kind: "rejected",
    });
  });

  it("maps an accepted company to an accepted chip", () => {
    expect(portfolioStatus(row({ gate: { status: "accepted" } }))).toEqual({
      text: "Accepted",
      kind: "accepted",
    });
  });

  it("labels a saved company as Saved to library even when rejected", () => {
    expect(
      portfolioStatus(row({ saved: true, gate: { status: "rejected" } }))
    ).toEqual({ text: "Saved to library", kind: "saved" });
  });
});

describe("portfolioProgress", () => {
  it("reports 0 for a fresh pending company", () => {
    expect(portfolioProgress(row({ gate: { status: "pending" } }))).toBe(0);
  });

  it("counts the gate as Step 1 done once accepted", () => {
    expect(portfolioProgress(row({ gate: { status: "accepted" } }))).toBe(1);
  });

  it("adds a step for each 2-4 done mark", () => {
    expect(
      portfolioProgress(row({ gate: { status: "accepted" }, done: { "2": true, "4": true } }))
    ).toBe(3);
  });

  it("counts a saved company as fully complete even with no done marks", () => {
    expect(portfolioProgress(row({ saved: true, done: {} }))).toBe(6);
  });

  it("exposes all six portfolio steps", () => {
    expect(PORTFOLIO_STEPS).toEqual([1, 2, 3, 4, 5, 6]);
  });
});
