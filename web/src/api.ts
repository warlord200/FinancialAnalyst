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

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, init);
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(detail || `Request failed: ${resp.status}`);
  }
  return resp.json() as Promise<T>;
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
