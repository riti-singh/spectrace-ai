import type { DashboardData, RetrievalMode, RetrievalResponse } from "../types";

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code?: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers }
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: { code?: string; message?: string } } | null;
    throw new ApiError(payload?.detail?.message ?? `Request failed (${response.status})`, response.status, payload?.detail?.code);
  }
  return response.json() as Promise<T>;
}

export async function loadDashboard(): Promise<DashboardData> {
  const [requirements, components, risks, tests, uncovered, summary, evaluation] = await Promise.all([
    request<DashboardData["requirements"]>("/requirements"),
    request<DashboardData["components"]>("/components"),
    request<DashboardData["risks"]>("/risks"),
    request<DashboardData["tests"]>("/test-cases"),
    request<DashboardData["uncovered"]>("/traceability/uncovered"),
    request<DashboardData["summary"]>("/traceability/summary"),
    request<DashboardData["evaluation"]>("/retrieval/evaluation")
  ]);
  return { requirements, components, risks, tests, uncovered, summary, evaluation };
}

export function searchTraceability(query: string, mode: RetrievalMode): Promise<RetrievalResponse> {
  return request<RetrievalResponse>("/retrieval/search", {
    method: "POST",
    body: JSON.stringify({ query, mode, result_count: 8, graph_depth: 2 })
  });
}
