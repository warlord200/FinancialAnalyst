import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { stepLockReason } from "./steps";
import { useDossier } from "./useDossier";

const ACCEPTED = { step: 1, status: "accepted" as const, updated_at: "2026-01-01T00:00:00Z" };

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  const state: Record<string, boolean> = {};
  return {
    ...actual,
    __resetDoneMarks: () => {
      for (const key of Object.keys(state)) delete state[key];
    },
    getNumbers: vi.fn(async () => {
      throw new Error("404");
    }),
    refreshNumbers: vi.fn(async () => ({})),
    getStepDone: vi.fn(async (ticker: string) => ({
      ticker,
      gate: ACCEPTED,
      done: { ...state },
    })),
    markStepDone: vi.fn(async (ticker: string, step: number) => {
      state[String(step)] = true;
      return { ticker, gate: ACCEPTED, done: { ...state } };
    }),
    clearStepDone: vi.fn(async (ticker: string, step: number) => {
      delete state[String(step)];
      return { ticker, gate: ACCEPTED, done: { ...state } };
    }),
  };
});

import * as api from "../api";

describe("done marks unlock Steps 5-6", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const reset = (api as unknown as { __resetDoneMarks?: () => void }).__resetDoneMarks;
    reset?.();
  });

  it("marking Steps 2-4 done unlocks Step 5", async () => {
    const { result } = renderHook(() => useDossier(() => {}));

    await act(() => result.current.loadProgress("TSLA"));
    expect(result.current.progress?.gate?.status).toBe("accepted");

    for (const step of [2, 3, 4]) {
      await act(() => result.current.toggleDone("TSLA", step, true));
    }

    const done = result.current.progress?.done ?? {};
    expect(done).toEqual({ "2": true, "3": true, "4": true });
    expect(stepLockReason(5, ACCEPTED, done)).toBeNull();

    const markSpy = api.markStepDone as ReturnType<typeof vi.fn>;
    const clearSpy = api.clearStepDone as ReturnType<typeof vi.fn>;
    expect(markSpy).toHaveBeenCalledTimes(3);
    expect(clearSpy).not.toHaveBeenCalled();
  });

  it("un-marking a done step re-locks Step 5 but keeps the other marks", async () => {
    const { result } = renderHook(() => useDossier(() => {}));

    await act(() => result.current.loadProgress("TSLA"));
    for (const step of [2, 3, 4]) {
      await act(() => result.current.toggleDone("TSLA", step, true));
    }

    await act(() => result.current.toggleDone("TSLA", 2, false));

    const done = result.current.progress?.done ?? {};
    expect(done).toEqual({ "3": true, "4": true });
    expect(stepLockReason(5, ACCEPTED, done)).not.toBeNull();
    expect(api.clearStepDone).toHaveBeenCalledWith("TSLA", 2);
  });
});
