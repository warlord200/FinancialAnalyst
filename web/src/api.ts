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

export type TagLabel = "bullish" | "neutral" | "bearish";

export interface OnePager {
  latest_fiscal_year: number | null;
  source: string;
  growth: {
    latest_revenue: number | null;
    revenue_growth_yoy: number | null;
    revenue_cagr_5y: number | null;
  };
  profitability: {
    gross_margin: number | null;
    operating_margin: number | null;
    net_margin: number | null;
  };
  debt: {
    debt_to_assets: number | null;
    debt_to_equity: number | null;
  };
  tag: { label: TagLabel; score: number; rationale: string };
}

export interface StepGate {
  step: number;
  status: "accepted" | "rejected";
  updated_at: string;
}

export interface OnePagerResponse {
  ticker: string;
  one_pager: OnePager;
  gate: StepGate | null;
}

export interface GateResponse {
  ticker: string;
  gate: StepGate;
}

export type SourceTagType = "fiscal_year" | "filing" | "item" | "xbrl_fact";

export interface SourceTag {
  type: SourceTagType;
  value: string;
}

export interface ArtifactSection {
  key: string;
  heading: string;
  content: string;
  sources: SourceTag[];
  evidence: string[];
}

export interface ArtifactScope {
  items: string[];
  fiscal_year: number | null;
}

export interface Artifact {
  ticker: string;
  artifact_type: string;
  fiscal_year: number | null;
  scope: ArtifactScope;
  generated_at: string;
  sections: ArtifactSection[];
}

export interface BusinessSwotResponse {
  ticker: string;
  artifact: Artifact;
  cached: boolean;
}

export type TableUnit = "percent" | "ratio";

export interface TableRow {
  label: string;
  values: Record<string, number | null>;
  sources: SourceTag[];
}

export interface FinancialTable {
  key: string;
  title: string;
  columns: string[];
  rows: TableRow[];
  unit: TableUnit;
  column_labels?: Record<string, string>;
}

export interface FinancialsArtifact extends Artifact {
  tables: FinancialTable[];
}

export interface FinancialsResponse {
  ticker: string;
  artifact: FinancialsArtifact;
  cached: boolean;
}

export interface StrategyArtifact extends Artifact {
  returns: FinancialTable | null;
}

export interface StrategyResponse {
  ticker: string;
  artifact: StrategyArtifact;
  cached: boolean;
}

export interface PeerScorecardResponse {
  ticker: string;
  peers: string[];
  scorecard: FinancialTable[];
}

export interface DoneMarksResponse {
  ticker: string;
  done: Record<string, boolean>;
}

export interface DcfSensitivityRow {
  discount_rate: number;
  values: Record<string, number | null>;
}

export interface DcfOutput {
  base_fiscal_year: string;
  fcf: number;
  discount_rate: number;
  growth: number;
  net_debt: number;
  enterprise_value: number;
  equity_value: number;
  equity_value_per_share: number | null;
  sensitivity: {
    discount_rates: number[];
    growth_rates: number[];
    rows: DcfSensitivityRow[];
  };
}

export interface MarketMultiples {
  fiscal_year: number | null;
  price: number | null;
  market_cap: number | null;
  enterprise_value: number | null;
  net_debt: number;
  eps: number | null;
  pe: number | null;
  ebitda: number | null;
  ev_ebitda: number | null;
  fcf: number | null;
  fcf_yield: number | null;
}

export interface HistoricalMultiples extends MarketMultiples {
  fiscal_year: number;
  end_date: string;
}

export interface PeerMultiples extends MarketMultiples {
  ticker: string;
}

export interface ValuationOutput {
  dcf: DcfOutput | null;
  multiples: MarketMultiples;
  history: HistoricalMultiples[];
  peers: PeerMultiples[];
}

export interface ValuationResponse {
  ticker: string;
  locked: boolean;
  done: Record<string, boolean>;
  missing_steps: number[];
  valuation?: ValuationOutput;
}

export interface ChatSource {
  text: string;
  item: string | null;
  fiscal_year: number | null;
  ticker: string;
  filing: string | null;
}

export interface ChatResponse {
  ticker: string;
  step: number;
  search_all: boolean;
  scope: { items: string[] | null; fiscal_year: number | null };
  answer: string;
  evidence: string[];
  sources: ChatSource[];
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

export function getOnePager(ticker: string) {
  return request<OnePagerResponse>(`/api/steps/${ticker}/one-pager`);
}

export function setStepGate(ticker: string, decision: "accept" | "reject") {
  return request<GateResponse>(`/api/steps/${ticker}/gate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
}

export function getBusinessSwot(ticker: string) {
  return request<BusinessSwotResponse>(`/api/steps/${ticker}/business-swot`);
}

export function getFinancials(ticker: string) {
  return request<FinancialsResponse>(`/api/steps/${ticker}/financials`);
}

export function getStrategy(ticker: string) {
  return request<StrategyResponse>(`/api/steps/${ticker}/strategy`);
}

export function getPeers(ticker: string) {
  return request<PeerScorecardResponse>(`/api/steps/${ticker}/peers`);
}

export function setPeers(ticker: string, peers: string[]) {
  return request<PeerScorecardResponse>(`/api/steps/${ticker}/peers`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ peers }),
  });
}

export function clearPeers(ticker: string) {
  return request<PeerScorecardResponse>(`/api/steps/${ticker}/peers`, {
    method: "DELETE",
  });
}

export function markStepDone(ticker: string, step: number) {
  return request<DoneMarksResponse>(`/api/steps/${ticker}/done/${step}`, {
    method: "POST",
  });
}

export function clearStepDone(ticker: string, step: number) {
  return request<DoneMarksResponse>(`/api/steps/${ticker}/done/${step}`, {
    method: "DELETE",
  });
}

export function getValuation(
  ticker: string,
  discountRate?: number,
  growth?: number
) {
  const params = new URLSearchParams();
  if (discountRate !== undefined) params.set("discount_rate", String(discountRate));
  if (growth !== undefined) params.set("growth", String(growth));
  const query = params.toString();
  return request<ValuationResponse>(
    `/api/steps/${ticker}/valuation${query ? `?${query}` : ""}`
  );
}

export function chatStep(
  ticker: string,
  step: number,
  question: string,
  searchAll = false
) {
  return request<ChatResponse>(`/api/steps/${ticker}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ step, question, search_all: searchAll }),
  });
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
