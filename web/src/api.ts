export type IngestJobStatus = "queued" | "running" | "completed" | "failed";

export interface IngestStats {
  ticker: string;
  ingested_at: string;
  num_chunks: number;
  chunks_by_item: Record<string, number>;
  chunks_by_year: Record<string, number>;
  fiscal_years: number[];
}

export interface IngestJob {
  id: string;
  ticker: string;
  status: IngestJobStatus;
  progress: number;
  result?: IngestStats | null;
  error?: string | null;
}

export interface IngestResponse {
  status: "submitted" | "cached";
  ticker: string;
  job_id?: string;
  ingested_at?: string;
}

export interface IngestedTicker {
  ticker: string;
  ingested_at?: string;
  num_chunks?: number;
  fiscal_years?: number[];
}

export interface Financials {
  fiscal_years: number[];
  income_statement: Record<string, Record<string, number>>;
  balance_sheet: Record<string, Record<string, number>>;
  cash_flow: Record<string, Record<string, number>>;
  common_size: {
    income_statement: Record<string, Record<string, number>>;
    balance_sheet: Record<string, Record<string, number>>;
  };
  ratios: Record<string, Record<string, number>>;
  cagr: Record<string, Record<string, number>>;
}

export interface PriceInfo {
  effective: { price: number; source: string; as_of: string };
  fetched: { price: number; as_of: string };
  override: { price: number; set_at: string } | null;
  history: { date: string; close: number }[];
}

export interface NumbersResponse {
  ticker: string;
  refreshed_at: string;
  financials: Financials;
  price: PriceInfo | null;
}

export interface AuthUser {
  email: string;
  verified: boolean;
  created_at: string;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

export interface QuotaState {
  used: number;
  limit: number;
  remaining: number;
}

export interface QuotaStatus {
  analyses: QuotaState;
  chat: QuotaState;
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const TOKEN_KEY = "fa_token";

export function setToken(token: string | null) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };
  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(detail || `Request failed: ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

export function signup(email: string, password: string) {
  return request<AuthResponse>("/api/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function login(email: string, password: string) {
  return request<AuthResponse>("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function logout() {
  return request<{ status: string }>("/api/auth/logout", { method: "POST" });
}

export function getMe() {
  return request<AuthUser>("/api/auth/me");
}

export function getQuota() {
  return request<QuotaStatus>("/api/auth/quota");
}

export function ingestTicker(ticker: string) {
  return request<IngestResponse>(`/api/ingest/${ticker}`, { method: "POST" });
}

export function getIngestJob(jobId: string) {
  return request<IngestJob>(`/api/ingest/jobs/${jobId}`);
}

export function listIngested() {
  return request<IngestedTicker[]>("/api/ingest");
}

export function getIngestStats(ticker: string) {
  return request<IngestStats>(`/api/ingest/${ticker}/stats`);
}

export function refreshNumbers(ticker: string) {
  return request<NumbersResponse>(`/api/numbers/${ticker}/refresh`, {
    method: "POST",
  });
}

export function getNumbers(ticker: string) {
  return request<NumbersResponse>(`/api/numbers/${ticker}`);
}

export function setPriceOverride(ticker: string, price: number) {
  return request<NumbersResponse>(`/api/numbers/${ticker}/price`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ price }),
  });
}

export function clearPriceOverride(ticker: string) {
  return request<NumbersResponse>(`/api/numbers/${ticker}/price`, {
    method: "DELETE",
  });
}
