// Server-side API client for the ShadowInvestor Railway API.
// All functions are intended to be called from Server Components / route
// handlers — they read API_BASE_URL and API_TOKEN from server-only env vars.

import type {
  Signal,
  Decision,
  Ticker,
  Portfolio,
  SourceHealth,
  DigestSummary,
  Digest,
  PipelineRun,
  Status,
  ResearchSector,
  ResearchRun,
  Position,
} from "./types";

const API_BASE = process.env.API_BASE_URL || "http://localhost:8765";
const API_TOKEN = process.env.API_TOKEN || "";

class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function apiFetch<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init.headers as Record<string, string>) || {}),
  };
  if (API_TOKEN) {
    headers["Authorization"] = `Bearer ${API_TOKEN}`;
  }
  const res = await fetch(url, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(`API ${res.status}: ${body || res.statusText}`, res.status);
  }
  return (await res.json()) as T;
}

// ============================================================================
// Public functions
// ============================================================================

export async function getStatus(): Promise<Status> {
  return apiFetch<Status>("/api/status");
}

export async function getSignals(params: {
  days?: number;
  minConviction?: number;
  sector?: string;
} = {}): Promise<Signal[]> {
  const qs = new URLSearchParams();
  if (params.days != null) qs.set("days", String(params.days));
  if (params.minConviction != null) qs.set("min_conviction", String(params.minConviction));
  if (params.sector != null) qs.set("sector", params.sector);
  const suffix = qs.toString() ? `?${qs}` : "";
  return apiFetch<Signal[]>(`/api/signals${suffix}`);
}

export async function getSignal(id: number): Promise<Signal> {
  return apiFetch<Signal>(`/api/signals/${id}`);
}

export async function getDecisions(params: {
  days?: number;
  mode?: string;
  action?: string;
  limit?: number;
} = {}): Promise<Decision[]> {
  const qs = new URLSearchParams();
  if (params.days != null) qs.set("days", String(params.days));
  if (params.mode != null) qs.set("mode", params.mode);
  if (params.action != null) qs.set("action", params.action);
  if (params.limit != null) qs.set("limit", String(params.limit));
  const suffix = qs.toString() ? `?${qs}` : "";
  return apiFetch<Decision[]>(`/api/decisions${suffix}`);
}

export async function getTickers(watchlistOnly = false): Promise<Ticker[]> {
  const suffix = watchlistOnly ? "?watchlist_only=true" : "";
  return apiFetch<Ticker[]>(`/api/tickers${suffix}`);
}

export async function getTicker(symbol: string): Promise<Ticker> {
  return apiFetch<Ticker>(`/api/tickers/${encodeURIComponent(symbol)}`);
}

export async function getTickerSignals(symbol: string, limit = 50): Promise<Signal[]> {
  return apiFetch<Signal[]>(`/api/tickers/${encodeURIComponent(symbol)}/signals?limit=${limit}`);
}

export async function getPortfolio(mode = "shadow"): Promise<Portfolio> {
  return apiFetch<Portfolio>(`/api/portfolio?mode=${mode}`);
}

export async function getSourcesHealth(): Promise<SourceHealth[]> {
  return apiFetch<SourceHealth[]>(`/api/sources`);
}

export async function getDigests(limit = 20): Promise<DigestSummary[]> {
  return apiFetch<DigestSummary[]>(`/api/digests?limit=${limit}`);
}

export async function getDigest(id: number): Promise<Digest> {
  return apiFetch<Digest>(`/api/digests/${id}`);
}

export async function runPipeline(params: { windowHours?: number; silent?: boolean } = {}): Promise<PipelineRun> {
  const qs = new URLSearchParams();
  if (params.windowHours != null) qs.set("window_hours", String(params.windowHours));
  if (params.silent != null) qs.set("silent", String(params.silent));
  return apiFetch<PipelineRun>(`/api/pipeline/run?${qs}`, { method: "POST" });
}

export async function getResearchStatus(): Promise<ResearchSector[]> {
  return apiFetch<ResearchSector[]>("/api/research/status");
}

export async function runResearch(sector?: string): Promise<ResearchRun> {
  const qs = sector ? `?sector=${encodeURIComponent(sector)}` : "";
  return apiFetch<ResearchRun>(`/api/research/run${qs}`, { method: "POST" });
}

export async function addTicker(data: {
  symbol: string; exchange: string; name: string;
  sector: string; thesis: string; sub_sector?: string;
}): Promise<Ticker> {
  return apiFetch<Ticker>("/api/tickers", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTickerStatus(symbol: string, status: string, note?: string): Promise<void> {
  await apiFetch(`/api/tickers/${encodeURIComponent(symbol)}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status, note }),
  });
}

export async function updateTickerThesis(symbol: string, thesis: string): Promise<void> {
  await apiFetch(`/api/tickers/${encodeURIComponent(symbol)}/thesis`, {
    method: "PATCH",
    body: JSON.stringify({ thesis }),
  });
}

export async function removeTickerFromWatchlist(symbol: string): Promise<void> {
  await apiFetch(`/api/tickers/${encodeURIComponent(symbol)}/watchlist`, {
    method: "DELETE",
  });
}

export async function setSignalAction(signalId: number, action: string, note?: string): Promise<void> {
  await apiFetch(`/api/signals/${signalId}/action`, {
    method: "POST",
    body: JSON.stringify({ action, note }),
  });
}

export async function getPositions(mode = "shadow", status?: string): Promise<Position[]> {
  const qs = new URLSearchParams({ mode });
  if (status) qs.set("status", status);
  return apiFetch<Position[]>(`/api/positions?${qs}`);
}

export async function sellPosition(positionId: number, shares?: number, note?: string): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>(`/api/positions/${positionId}/sell`, {
    method: "POST",
    body: JSON.stringify({ shares, note }),
  });
}

export async function getDiscoveries(): Promise<Record<string, unknown>[]> {
  return apiFetch<Record<string, unknown>[]>("/api/discoveries");
}
