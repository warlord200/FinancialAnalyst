import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import type { LibraryRow } from "../api";
import { LibraryView } from "./libraryView";

const row = (ticker: string, savedAt: string): LibraryRow => ({
  ticker,
  saved_at: savedAt,
});

const ROWS = [
  row("TSLA", "2026-09-08T10:00:00Z"),
  row("MSFT", "2026-09-07T10:00:00Z"),
];

afterEach(cleanup);

function renderView(
  props: Partial<React.ComponentProps<typeof LibraryView>> = {}
) {
  return render(
    <LibraryView
      rows={[]}
      loading={false}
      error=""
      onOpen={vi.fn()}
      onUnsave={vi.fn()}
      {...props}
    />
  );
}

const rowFor = (container: HTMLElement, ticker: string) =>
  Array.from(container.querySelectorAll("tr.library-row")).find((r) =>
    r.textContent?.includes(ticker)
  );

describe("LibraryView", () => {
  it("renders one row per saved ticker showing the ticker and its saved date", () => {
    const { container } = renderView({ rows: ROWS });
    const tsla = rowFor(container, "TSLA");
    expect(tsla).toBeDefined();
    expect(tsla?.querySelector("strong")?.textContent).toBe("TSLA");
    expect(tsla?.querySelector(".meta-text")?.textContent).toBe("2026-09-08");
    expect(container.querySelectorAll("tr.library-row")).toHaveLength(2);
  });

  it("calls onOpen with the ticker when a row is clicked", () => {
    const onOpen = vi.fn();
    renderView({ rows: ROWS, onOpen });
    fireEvent.click(screen.getByText("MSFT"));
    expect(onOpen).toHaveBeenCalledWith("MSFT");
  });

  it("calls onOpen with the ticker when Enter is pressed on a row", () => {
    const onOpen = vi.fn();
    const { container } = renderView({ rows: ROWS, onOpen });
    fireEvent.keyDown(rowFor(container, "TSLA")!, { key: "Enter" });
    expect(onOpen).toHaveBeenCalledWith("TSLA");
  });

  it("calls onOpen with the ticker when Space is pressed on a row", () => {
    const onOpen = vi.fn();
    const { container } = renderView({ rows: ROWS, onOpen });
    fireEvent.keyDown(rowFor(container, "MSFT")!, { key: " " });
    expect(onOpen).toHaveBeenCalledWith("MSFT");
  });

  it("clicking Unsave calls onUnsave with the ticker and does not call onOpen", () => {
    const onOpen = vi.fn();
    const onUnsave = vi.fn();
    renderView({ rows: ROWS, onOpen, onUnsave });
    fireEvent.click(screen.getByLabelText("Unsave TSLA"));
    expect(onUnsave).toHaveBeenCalledWith("TSLA");
    expect(onOpen).not.toHaveBeenCalled();
  });

  it("shows the loading status while loading and renders no table", () => {
    const { container } = renderView({ loading: true });
    expect(screen.getByText("Loading library…")).toBeDefined();
    expect(container.querySelector("table")).toBeNull();
  });

  it("shows the error banner when not loading and an error is set", () => {
    const { container } = renderView({ error: "Library failed to load" });
    expect(screen.getByText("Library failed to load")).toBeDefined();
    expect(container.querySelector("table")).toBeNull();
  });

  it("shows an empty note when there are no rows", () => {
    const { container } = renderView({ rows: [] });
    expect(screen.getByText("Nothing saved yet.")).toBeDefined();
    expect(container.querySelector("table")).toBeNull();
  });
});
