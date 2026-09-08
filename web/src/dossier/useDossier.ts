import { useRef, useState } from "react";
import {
  clearStepDone,
  getBusinessSwot,
  getFinancials,
  getNumbers,
  getOnePager,
  getStepDone,
  getStrategy,
  getThesis,
  getValuation,
  markStepDone,
  refreshNumbers,
  setStepGate,
} from "../api";
import type {
  BusinessSwotResponse,
  DoneMarksResponse,
  FinancialsResponse,
  OnePagerResponse,
  StrategyResponse,
  ThesisResponse,
  ValuationResponse,
} from "../api";

type InflightKey = "onePager" | "business" | "financials" | "strategy" | "valuation" | "thesis";

export interface Dossier {
  progress: DoneMarksResponse | null;
  progressError: string;
  progressLoading: boolean;
  onePager: OnePagerResponse | null;
  onePagerError: string;
  onePagerLoading: boolean;
  business: BusinessSwotResponse | null;
  businessError: string;
  businessLoading: boolean;
  financials: FinancialsResponse | null;
  financialsError: string;
  financialsLoading: boolean;
  strategy: StrategyResponse | null;
  strategyError: string;
  strategyLoading: boolean;
  valuation: ValuationResponse | null;
  valuationError: string;
  valuationLoading: boolean;
  thesis: ThesisResponse | null;
  thesisError: string;
  thesisLoading: boolean;
  valDiscountPct: string;
  valGrowthPct: string;
  setValDiscountPct: (value: string) => void;
  setValGrowthPct: (value: string) => void;
  loadProgress: (symbol: string) => Promise<void>;
  loadOnePager: (symbol: string) => Promise<void>;
  setGate: (symbol: string, decision: "accept" | "reject") => Promise<void>;
  loadBusinessSwot: (symbol: string) => Promise<void>;
  loadFinancials: (symbol: string) => Promise<void>;
  loadStrategy: (symbol: string) => Promise<void>;
  loadValuation: (symbol: string) => Promise<void>;
  toggleDone: (symbol: string, step: number, done: boolean) => Promise<void>;
  loadThesis: (symbol: string) => Promise<void>;
  reset: () => void;
}

export function useDossier(onQuotaChange: () => void): Dossier {
  const [progress, setProgress] = useState<DoneMarksResponse | null>(null);
  const [progressError, setProgressError] = useState("");
  const [progressLoading, setProgressLoading] = useState(false);

  const [onePager, setOnePager] = useState<OnePagerResponse | null>(null);
  const [onePagerError, setOnePagerError] = useState("");
  const [onePagerLoading, setOnePagerLoading] = useState(false);

  const [business, setBusiness] = useState<BusinessSwotResponse | null>(null);
  const [businessError, setBusinessError] = useState("");
  const [businessLoading, setBusinessLoading] = useState(false);

  const [financials, setFinancials] = useState<FinancialsResponse | null>(null);
  const [financialsError, setFinancialsError] = useState("");
  const [financialsLoading, setFinancialsLoading] = useState(false);

  const [strategy, setStrategy] = useState<StrategyResponse | null>(null);
  const [strategyError, setStrategyError] = useState("");
  const [strategyLoading, setStrategyLoading] = useState(false);

  const [valuation, setValuation] = useState<ValuationResponse | null>(null);
  const [valuationError, setValuationError] = useState("");
  const [valuationLoading, setValuationLoading] = useState(false);

  const [thesis, setThesis] = useState<ThesisResponse | null>(null);
  const [thesisError, setThesisError] = useState("");
  const [thesisLoading, setThesisLoading] = useState(false);

  const [valDiscountPct, setValDiscountPct] = useState("10");
  const [valGrowthPct, setValGrowthPct] = useState("3");

  const inflight = useRef<Record<InflightKey, string | null>>({
    onePager: null,
    business: null,
    financials: null,
    strategy: null,
    valuation: null,
    thesis: null,
  });

  async function ensureNumbers(symbol: string) {
    try {
      await getNumbers(symbol);
    } catch {
      await refreshNumbers(symbol);
      onQuotaChange();
    }
  }

  async function loadProgress(symbol: string) {
    const s = symbol.trim().toUpperCase();
    if (!s) return;
    setProgressLoading(true);
    setProgressError("");
    try {
      await ensureNumbers(s);
      setProgress(await getStepDone(s));
    } catch (e) {
      setProgressError(e instanceof Error ? e.message : "Failed to load dossier progress");
    } finally {
      setProgressLoading(false);
    }
  }

  async function loadOnePager(symbol: string) {
    const s = symbol.trim().toUpperCase();
    if (!s || inflight.current.onePager === s) return;
    inflight.current.onePager = s;
    setOnePagerLoading(true);
    setOnePagerError("");
    try {
      await ensureNumbers(s);
      setOnePager(await getOnePager(s));
    } catch (e) {
      setOnePagerError(e instanceof Error ? e.message : "Failed to load one-pager");
    } finally {
      inflight.current.onePager = null;
      setOnePagerLoading(false);
    }
  }

  async function setGate(symbol: string, decision: "accept" | "reject") {
    if (!onePager && !progress) return;
    setOnePagerError("");
    setProgressError("");
    try {
      const res = await setStepGate(symbol, decision);
      setOnePager((prev) => (prev ? { ...prev, gate: res.gate } : prev));
      setProgress((prev) => (prev ? { ...prev, gate: res.gate } : prev));
    } catch (e) {
      setOnePagerError(e instanceof Error ? e.message : "Failed to save decision");
    }
  }

  function clearGatedSteps() {
    setValuation(null);
    setValuationError("");
    setThesis(null);
    setThesisError("");
  }

  async function loadBusinessSwot(symbol: string) {
    const s = symbol.trim().toUpperCase();
    if (!s || inflight.current.business === s) return;
    inflight.current.business = s;
    setBusinessLoading(true);
    setBusinessError("");
    try {
      setBusiness(await getBusinessSwot(s));
    } catch (e) {
      setBusinessError(e instanceof Error ? e.message : "Failed to load business & SWOT");
    } finally {
      inflight.current.business = null;
      setBusinessLoading(false);
    }
  }

  async function loadFinancials(symbol: string) {
    const s = symbol.trim().toUpperCase();
    if (!s || inflight.current.financials === s) return;
    inflight.current.financials = s;
    setFinancialsLoading(true);
    setFinancialsError("");
    try {
      await ensureNumbers(s);
      setFinancials(await getFinancials(s));
    } catch (e) {
      setFinancialsError(e instanceof Error ? e.message : "Failed to load financials");
    } finally {
      inflight.current.financials = null;
      setFinancialsLoading(false);
    }
  }

  async function loadStrategy(symbol: string) {
    const s = symbol.trim().toUpperCase();
    if (!s || inflight.current.strategy === s) return;
    inflight.current.strategy = s;
    setStrategyLoading(true);
    setStrategyError("");
    try {
      await ensureNumbers(s);
      setStrategy(await getStrategy(s));
    } catch (e) {
      setStrategyError(e instanceof Error ? e.message : "Failed to load strategy");
    } finally {
      inflight.current.strategy = null;
      setStrategyLoading(false);
    }
  }

  function currentAssumptionParams() {
    const d = parseFloat(valDiscountPct) / 100;
    const g = parseFloat(valGrowthPct) / 100;
    return {
      discountRate: Number.isFinite(d) ? d : undefined,
      growth: Number.isFinite(g) ? g : undefined,
    };
  }

  async function loadValuation(symbol: string) {
    const s = symbol.trim().toUpperCase();
    if (!s || inflight.current.valuation === s) return;
    inflight.current.valuation = s;
    setValuationLoading(true);
    setValuationError("");
    const { discountRate, growth } = currentAssumptionParams();
    try {
      await ensureNumbers(s);
      setValuation(await getValuation(s, discountRate, growth));
    } catch (e) {
      setValuationError(e instanceof Error ? e.message : "Failed to load valuation");
    } finally {
      inflight.current.valuation = null;
      setValuationLoading(false);
    }
  }

  async function toggleDone(symbol: string, step: number, done: boolean) {
    setProgressError("");
    try {
      const updated = done
        ? await clearStepDone(symbol, step)
        : await markStepDone(symbol, step);
      setProgress(updated);
      clearGatedSteps();
    } catch (e) {
      setProgressError(e instanceof Error ? e.message : "Failed to save done mark");
    }
  }

  async function loadThesis(symbol: string) {
    const s = symbol.trim().toUpperCase();
    if (!s || inflight.current.thesis === s) return;
    inflight.current.thesis = s;
    setThesisLoading(true);
    setThesisError("");
    try {
      await ensureNumbers(s);
      setThesis(await getThesis(s));
    } catch (e) {
      setThesisError(e instanceof Error ? e.message : "Failed to load thesis");
    } finally {
      inflight.current.thesis = null;
      setThesisLoading(false);
    }
  }

  function reset() {
    inflight.current = {
      onePager: null,
      business: null,
      financials: null,
      strategy: null,
      valuation: null,
      thesis: null,
    };
    setProgress(null);
    setProgressError("");
    setProgressLoading(false);
    setOnePager(null);
    setOnePagerError("");
    setOnePagerLoading(false);
    setBusiness(null);
    setBusinessError("");
    setBusinessLoading(false);
    setFinancials(null);
    setFinancialsError("");
    setFinancialsLoading(false);
    setStrategy(null);
    setStrategyError("");
    setStrategyLoading(false);
    setValuation(null);
    setValuationError("");
    setValuationLoading(false);
    setThesis(null);
    setThesisError("");
    setThesisLoading(false);
  }

  return {
    progress,
    progressError,
    progressLoading,
    onePager,
    onePagerError,
    onePagerLoading,
    business,
    businessError,
    businessLoading,
    financials,
    financialsError,
    financialsLoading,
    strategy,
    strategyError,
    strategyLoading,
    valuation,
    valuationError,
    valuationLoading,
    thesis,
    thesisError,
    thesisLoading,
    valDiscountPct,
    valGrowthPct,
    setValDiscountPct,
    setValGrowthPct,
    loadProgress,
    loadOnePager,
    setGate,
    loadBusinessSwot,
    loadFinancials,
    loadStrategy,
    loadValuation,
    toggleDone,
    loadThesis,
    reset,
  };
}
