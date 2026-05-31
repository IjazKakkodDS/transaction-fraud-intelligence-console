import { apiFetch } from "@/lib/api/client";
import { ApiError } from "@/types/api";
import {
  type RecentScan,
  type RiskScanPromoteResponse,
  type RiskScanPaginatedResults,
  type RiskScanResultsFilters,
  type RiskScanStatus,
  type RiskScanSummary,
  type RiskScanUploadResponse,
  RecentScanListSchema,
  RiskScanPromoteResponseSchema,
  RiskScanPaginatedResultsSchema,
  RiskScanStatusSchema,
  RiskScanSummarySchema,
  RiskScanUploadResponseSchema,
} from "@/types/riskScan";

// Upload bypasses apiFetch because it does not send JSON.
// Derive BASE_URL from the same env var that client.ts uses.
const BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

// ---------------------------------------------------------------------------
// POST /risk-scan
// Sends the CSV as multipart/form-data. Content-Type must NOT be set manually
// — the browser adds the boundary parameter automatically.
// ---------------------------------------------------------------------------

export async function uploadRiskScan(
  file: File,
): Promise<RiskScanUploadResponse> {
  const form = new FormData();
  form.append("file", file);

  const response = await fetch(`${BASE_URL}/risk-scan`, {
    method: "POST",
    body: form,
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status} — ${response.statusText}`;
    try {
      const json = await response.json();
      if (typeof json?.detail === "string") detail = json.detail;
    } catch {
      // Response body was not JSON.
    }
    throw new ApiError(response.status, detail);
  }

  const data: unknown = await response.json();
  return RiskScanUploadResponseSchema.parse(data);
}

// ---------------------------------------------------------------------------
// GET /risk-scan/{scan_id}/status
// ---------------------------------------------------------------------------

export async function fetchRiskScanStatus(
  scanId: string,
): Promise<RiskScanStatus> {
  return apiFetch<RiskScanStatus>(`/risk-scan/${scanId}/status`, {
    schema: RiskScanStatusSchema,
  });
}

// ---------------------------------------------------------------------------
// GET /risk-scan/{scan_id}/summary
// ---------------------------------------------------------------------------

export async function fetchRiskScanSummary(
  scanId: string,
): Promise<RiskScanSummary> {
  return apiFetch<RiskScanSummary>(`/risk-scan/${scanId}/summary`, {
    schema: RiskScanSummarySchema,
  });
}

// ---------------------------------------------------------------------------
// GET /risk-scan/{scan_id}/results
// Optional filters map to query params; only defined values are included.
// promoted is serialised as "true"/"false" so the backend bool parser fires.
// ---------------------------------------------------------------------------

export async function fetchRiskScanResults(
  scanId: string,
  filters?: RiskScanResultsFilters,
  page?: number,
  pageSize?: number,
): Promise<RiskScanPaginatedResults> {
  const params = new URLSearchParams();

  if (filters?.tier !== undefined) {
    params.set("tier", filters.tier);
  }
  if (filters?.decision !== undefined) {
    params.set("decision", filters.decision);
  }
  if (filters?.validation_status !== undefined) {
    params.set("validation_status", filters.validation_status);
  }
  if (filters?.promoted !== undefined) {
    params.set("promoted", String(filters.promoted));
  }
  params.set("page", String(page ?? 1));
  params.set("page_size", String(pageSize ?? 100));

  const query = params.toString();
  const path = `/risk-scan/${scanId}/results${query ? `?${query}` : ""}`;

  return apiFetch<RiskScanPaginatedResults>(path, {
    schema: RiskScanPaginatedResultsSchema,
  });
}

// ---------------------------------------------------------------------------
// POST /risk-scan/{scan_id}/promote/{result_id}
// No request body — the backend uses only server-side stored row data.
// ---------------------------------------------------------------------------

export async function promoteRiskScanResult(
  scanId: string,
  resultId: number,
): Promise<RiskScanPromoteResponse> {
  return apiFetch<RiskScanPromoteResponse>(
    `/risk-scan/${scanId}/promote/${resultId}`,
    {
      method: "POST",
      schema: RiskScanPromoteResponseSchema,
    },
  );
}

// ---------------------------------------------------------------------------
// GET /risk-scan/{scan_id}/export
// Return a direct download URL so large streamed CSV exports stay out of
// JavaScript memory and use the browser download manager instead.
// ---------------------------------------------------------------------------

export function getRiskScanExportUrl(scanId: string): string {
  return `${BASE_URL}/risk-scan/${encodeURIComponent(scanId)}/export`;
}

// ---------------------------------------------------------------------------
// GET /risk-scan/recent
// Returns recent scan headers ordered newest-first. Does not fetch result rows.
// ---------------------------------------------------------------------------

export async function getRecentRiskScans(limit = 10): Promise<RecentScan[]> {
  const safeLimit = Math.min(50, Math.max(1, limit));
  return apiFetch<RecentScan[]>(`/risk-scan/recent?limit=${safeLimit}`, {
    schema: RecentScanListSchema,
  });
}
