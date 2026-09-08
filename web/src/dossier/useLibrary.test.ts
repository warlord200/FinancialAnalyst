import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useLibrary } from "./useLibrary";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  let store: { ticker: string; saved_at: string }[] = [];
  let saveSeq = 0;
  const base = Date.UTC(2026, 0, 1);
  const iso = (n: number) => new Date(base + n * 1000).toISOString();
  return {
    ...actual,
    __resetLibrary: () => {
      store = [];
      saveSeq = 0;
    },
    getLibrary: vi.fn(async () => [...store]),
    saveToLibrary: vi.fn(async (ticker: string) => {
      saveSeq += 1;
      const saved_at = iso(saveSeq);
      store = store.filter((row) => row.ticker !== ticker);
      store.unshift({ ticker, saved_at });
      return { ticker, saved: true, saved_at };
    }),
    unsaveFromLibrary: vi.fn(async (ticker: string) => {
      store = store.filter((row) => row.ticker !== ticker);
      return { ticker, saved: false, saved_at: null };
    }),
  };
});

import * as api from "../api";

describe("useLibrary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const reset = (api as unknown as { __resetLibrary?: () => void }).__resetLibrary;
    reset?.();
  });

  it("loads the library and reports saved tickers", async () => {
    const { result } = renderHook(() => useLibrary());

    await api.saveToLibrary("TSLA");
    await api.saveToLibrary("AAPL");

    await act(() => result.current.load());

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe("");
    expect(result.current.rows.map((row) => row.ticker)).toEqual(["AAPL", "TSLA"]);
    expect(result.current.isSaved("tsla")).toBe(true);
    expect(result.current.isSaved("MSFT")).toBe(false);
  });

  it("saves a ticker (normalised) and isSaved matches case-insensitively", async () => {
    const { result } = renderHook(() => useLibrary());

    await act(() => result.current.save(" tsla "));

    expect(api.saveToLibrary).toHaveBeenCalledWith("TSLA");
    expect(result.current.rows.map((row) => row.ticker)).toEqual(["TSLA"]);
    expect(result.current.isSaved("tsla")).toBe(true);
    expect(result.current.saving).toBe(false);
    expect(result.current.actionError).toBe("");
  });

  it("does not call the api again for an already-saved ticker", async () => {
    const { result } = renderHook(() => useLibrary());
    const saveSpy = api.saveToLibrary as ReturnType<typeof vi.fn>;

    await act(() => result.current.save("TSLA"));
    expect(saveSpy).toHaveBeenCalledTimes(1);

    await act(() => result.current.save("tsla"));
    expect(saveSpy).toHaveBeenCalledTimes(1);
    expect(result.current.rows).toHaveLength(1);
    expect(result.current.isSaved("TSLA")).toBe(true);
  });

  it("unsaves a ticker and isSaved flips false", async () => {
    const { result } = renderHook(() => useLibrary());

    await act(() => result.current.save("TSLA"));
    await act(() => result.current.save("AAPL"));

    await act(() => result.current.unsave("TSLA"));

    expect(api.unsaveFromLibrary).toHaveBeenCalledWith("TSLA");
    expect(result.current.isSaved("tsla")).toBe(false);
    expect(result.current.rows.map((row) => row.ticker)).toEqual(["AAPL"]);
    expect(result.current.saving).toBe(false);
  });

  it("keeps rows newest-saved first across mutations", async () => {
    const { result } = renderHook(() => useLibrary());

    await api.saveToLibrary("TSLA");
    await api.saveToLibrary("AAPL");
    await act(() => result.current.load());
    expect(result.current.rows.map((row) => row.ticker)).toEqual(["AAPL", "TSLA"]);

    await act(() => result.current.unsave("AAPL"));
    await act(() => result.current.save("AAPL"));
    expect(result.current.rows.map((row) => row.ticker)).toEqual(["AAPL", "TSLA"]);

    await act(() => result.current.save("MSFT"));
    expect(result.current.rows.map((row) => row.ticker)).toEqual(["MSFT", "AAPL", "TSLA"]);
  });

  it("surfaces a load error and keeps the previous rows", async () => {
    const { result } = renderHook(() => useLibrary());

    await act(() => result.current.save("TSLA"));
    const getSpy = api.getLibrary as ReturnType<typeof vi.fn>;
    getSpy.mockRejectedValueOnce(new Error("boom"));

    await act(() => result.current.load());

    expect(result.current.error).toBe("boom");
    expect(result.current.rows.map((row) => row.ticker)).toEqual(["TSLA"]);
    expect(result.current.loading).toBe(false);
  });

  it("surfaces a save error and does not mutate rows", async () => {
    const { result } = renderHook(() => useLibrary());

    await act(() => result.current.save("AAPL"));
    const saveSpy = api.saveToLibrary as ReturnType<typeof vi.fn>;
    saveSpy.mockRejectedValueOnce(new Error("quota"));

    await act(() => result.current.save("TSLA"));

    expect(result.current.actionError).toBe("quota");
    expect(result.current.rows.map((row) => row.ticker)).toEqual(["AAPL"]);
    expect(result.current.isSaved("TSLA")).toBe(false);
    expect(result.current.saving).toBe(false);
  });

  it("reset clears rows, flags, and errors", async () => {
    const { result } = renderHook(() => useLibrary());
    const getSpy = api.getLibrary as ReturnType<typeof vi.fn>;
    const saveSpy = api.saveToLibrary as ReturnType<typeof vi.fn>;

    await act(() => result.current.save("TSLA"));
    getSpy.mockRejectedValueOnce(new Error("boom"));
    await act(() => result.current.load());
    saveSpy.mockRejectedValueOnce(new Error("quota"));
    await act(() => result.current.save("AAPL"));

    expect(result.current.error).toBe("boom");
    expect(result.current.actionError).toBe("quota");

    act(() => result.current.reset());

    expect(result.current.rows).toEqual([]);
    expect(result.current.error).toBe("");
    expect(result.current.actionError).toBe("");
    expect(result.current.loading).toBe(false);
    expect(result.current.saving).toBe(false);
    expect(result.current.isSaved("TSLA")).toBe(false);
  });
});
