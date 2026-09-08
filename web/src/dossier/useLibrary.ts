import { useState } from "react";
import { getLibrary, saveToLibrary, unsaveFromLibrary } from "../api";
import type { LibraryRow } from "../api";

export interface Library {
  rows: LibraryRow[];
  loading: boolean;
  error: string;
  saving: boolean;
  actionError: string;
  isSaved: (ticker: string) => boolean;
  load: () => Promise<void>;
  save: (ticker: string) => Promise<void>;
  unsave: (ticker: string) => Promise<void>;
  reset: () => void;
}

export function useLibrary(): Library {
  const [rows, setRows] = useState<LibraryRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState("");

  function isSaved(ticker: string) {
    const t = ticker.trim().toUpperCase();
    return rows.some((row) => row.ticker.toUpperCase() === t);
  }

  function newestFirst(list: LibraryRow[]) {
    return [...list].sort((a, b) => {
      if (a.saved_at === b.saved_at) return a.ticker < b.ticker ? -1 : 1;
      return a.saved_at > b.saved_at ? -1 : 1;
    });
  }

  async function load() {
    setLoading(true);
    setError("");
    try {
      setRows(await getLibrary());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load library");
    } finally {
      setLoading(false);
    }
  }

  async function save(ticker: string) {
    const t = ticker.trim().toUpperCase();
    if (isSaved(t)) return;
    setSaving(true);
    setActionError("");
    try {
      const res = await saveToLibrary(t);
      setRows((prev) => {
        const previous = prev.find((row) => row.ticker.toUpperCase() === t);
        const next = prev.filter((row) => row.ticker.toUpperCase() !== t);
        next.push({
          ticker: t,
          saved_at: res.saved_at ?? previous?.saved_at ?? new Date().toISOString(),
        });
        return newestFirst(next);
      });
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to save to library");
    } finally {
      setSaving(false);
    }
  }

  async function unsave(ticker: string) {
    const t = ticker.trim().toUpperCase();
    setSaving(true);
    setActionError("");
    try {
      await unsaveFromLibrary(t);
      setRows((prev) => prev.filter((row) => row.ticker.toUpperCase() !== t));
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to unsave");
    } finally {
      setSaving(false);
    }
  }

  function reset() {
    setRows([]);
    setLoading(false);
    setError("");
    setSaving(false);
    setActionError("");
  }

  return {
    rows,
    loading,
    error,
    saving,
    actionError,
    isSaved,
    load,
    save,
    unsave,
    reset,
  };
}
