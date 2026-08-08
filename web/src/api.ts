export interface Verdict {
  label: "bullish" | "neutral" | "bearish";
  score: number;
  rationale: string;
}

export interface ReportData {
  ticker: string;
  fiscal_years: number[];
  generated_at: string;
  verdict: Verdict;
  markdown: string;
}

export interface TickerInfo {
  ticker: string;
  fiscal_years: number[];
  report_generated_at?: string;
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, init);
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(detail || `Request failed: ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

export function analyzeTicker(ticker: string) {
  return request<{ status: string; report_path: string }>(
    `/api/analyze/${ticker}`,
    { method: "POST" }
  );
}

export function reanalyzeTicker(ticker: string) {
  return request<{ status: string; report_path: string }>(
    `/api/reanalyze/${ticker}`,
    { method: "POST" }
  );
}

export function getReport(ticker: string) {
  return request<ReportData>(`/api/report/${ticker}`);
}

export function listTickers() {
  return request<TickerInfo[]>("/api/tickers");
}
