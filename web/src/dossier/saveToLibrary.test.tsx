import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { SaveToLibrary } from "./saveToLibrary";

afterEach(cleanup);

const baseProps = {
  saved: false,
  busy: false,
  error: "",
  onSave: vi.fn(),
  onUnsave: vi.fn(),
};

describe("SaveToLibrary", () => {
  it("when unsaved, shows a Save to library button that fires onSave and not onUnsave", () => {
    const onSave = vi.fn();
    const onUnsave = vi.fn();
    render(<SaveToLibrary {...baseProps} onSave={onSave} onUnsave={onUnsave} />);
    const button = screen.getByRole("button", { name: "Save to library" });
    fireEvent.click(button);
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onUnsave).not.toHaveBeenCalled();
  });

  it("when saved, shows the saved badge and no Save to library button; Unsave fires onUnsave and not onSave", () => {
    const onSave = vi.fn();
    const onUnsave = vi.fn();
    render(
      <SaveToLibrary
        {...baseProps}
        saved={true}
        onSave={onSave}
        onUnsave={onUnsave}
      />
    );
    expect(screen.getByText("✓ Saved to library")).toBeDefined();
    expect(screen.queryByRole("button", { name: "Save to library" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Unsave" }));
    expect(onUnsave).toHaveBeenCalledTimes(1);
    expect(onSave).not.toHaveBeenCalled();
  });

  it("busy disables the Save to library button when unsaved", () => {
    render(<SaveToLibrary {...baseProps} busy={true} />);
    expect(
      (screen.getByRole("button", { name: "Save to library" }) as HTMLButtonElement)
        .disabled
    ).toBe(true);
  });

  it("busy disables the Unsave button when saved", () => {
    render(<SaveToLibrary {...baseProps} saved={true} busy={true} />);
    expect(
      (screen.getByRole("button", { name: "Unsave" }) as HTMLButtonElement).disabled
    ).toBe(true);
  });

  it("renders the error banner text when error is non-empty", () => {
    render(<SaveToLibrary {...baseProps} error="Could not save" />);
    expect(screen.getByText("Could not save")).toBeDefined();
  });
});
