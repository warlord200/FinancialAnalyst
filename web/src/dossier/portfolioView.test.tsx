import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import type { PortfolioRow } from "../api";
import { PortfolioView } from "./portfolioView";

const row = (ticker: string, over: Partial<PortfolioRow> = {}): PortfolioRow => ({
  ticker,
  ingested_at: null,
  numbers_ready: false,
  gate: { status: "pending" },
  done: {},
  saved: false,
  ...over,
});

const MIXED = [
  row("TSLA", { gate: { status: "pending" } }),
  row("MSFT", { gate: { status: "accepted" }, done: { "2": true } }),
  row("GOOGL", { gate: { status: "rejected" } }),
  row("AAPL", { saved: true, gate: { status: "accepted" } }),
];

afterEach(cleanup);

function renderView(
  props: Partial<React.ComponentProps<typeof PortfolioView>> = {}
) {
  return render(
    <PortfolioView
      rows={[]}
      loading={false}
      error=""
      onOpenCompany={vi.fn()}
      {...props}
    />
  );
}

const rowFor = (container: HTMLElement, ticker: string) =>
  Array.from(container.querySelectorAll("tr.portfolio-row")).find((r) =>
    r.textContent?.includes(ticker)
  );

const dotCounts = (r: Element) => ({
  total: r.querySelectorAll(".pdot").length,
  on: r.querySelectorAll(".pdot.on").length,
});

describe("PortfolioView", () => {
  it("renders one row per ticker with the right status chip", () => {
    const { container } = renderView({ rows: MIXED });
    for (const [ticker, chip] of [
      ["TSLA", "Gate pending"],
      ["MSFT", "Accepted"],
      ["GOOGL", "Rejected"],
      ["AAPL", "Saved to library"],
    ] as const) {
      const r = rowFor(container, ticker);
      expect(r).toBeDefined();
      expect(r?.querySelector(".status-chip")?.textContent).toBe(chip);
    }
    expect(container.querySelectorAll("tr.portfolio-row")).toHaveLength(4);
  });

  it("renders six dots per row, lighting only the completed steps", () => {
    const { container } = renderView({ rows: MIXED });
    expect(dotCounts(rowFor(container, "TSLA")!)).toEqual({ total: 6, on: 0 });
    expect(dotCounts(rowFor(container, "MSFT")!)).toEqual({ total: 6, on: 2 });
    expect(dotCounts(rowFor(container, "GOOGL")!)).toEqual({ total: 6, on: 0 });
    expect(dotCounts(rowFor(container, "AAPL")!)).toEqual({ total: 6, on: 6 });
  });

  it("calls onOpenCompany with the ticker when a row is clicked", () => {
    const onOpenCompany = vi.fn();
    renderView({ rows: MIXED, onOpenCompany });
    fireEvent.click(screen.getByText("MSFT"));
    expect(onOpenCompany).toHaveBeenCalledWith("MSFT");
  });

  it("shows the loading status while loading", () => {
    const { container } = renderView({ loading: true });
    expect(screen.getByText("Loading portfolio…")).toBeDefined();
    expect(container.querySelector("table")).toBeNull();
  });

  it("shows the error banner when not loading and an error is set", () => {
    const { container } = renderView({ error: "Portfolio failed to load" });
    expect(screen.getByText("Portfolio failed to load")).toBeDefined();
    expect(container.querySelector("table")).toBeNull();
  });

  it("shows an empty note when there are no rows", () => {
    const { container } = renderView({ rows: [] });
    expect(screen.getByText("Nothing ingested yet.")).toBeDefined();
    expect(container.querySelector("table")).toBeNull();
  });
});
