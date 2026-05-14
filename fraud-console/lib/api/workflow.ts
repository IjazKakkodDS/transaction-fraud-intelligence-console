import { apiFetch } from "@/lib/api/client";
import {
  type DailySummary,
  type NotifyCaseResponse,
  type StaleCasesResponse,
  type WorkflowEvents,
  type WorkflowMetrics,
  DailySummarySchema,
  NotifyCaseResponseSchema,
  StaleCasesResponseSchema,
  WorkflowEventsSchema,
  WorkflowMetricsSchema,
} from "@/types/workflow";

/**
 * POST /workflow/notify-case/{caseId}
 *
 * Dispatches the fraud case payload to the configured n8n webhook URL.
 * The backend builds the payload from the case and its latest investigation
 * — no request body is required from the frontend.
 * Throws ApiError 503 if N8N_WEBHOOK_URL is not configured on the backend,
 * or 502 if n8n is unreachable or returns a non-2xx response.
 */
export async function notifyCase(
  caseId: number,
): Promise<NotifyCaseResponse> {
  return apiFetch<NotifyCaseResponse>(`/workflow/notify-case/${caseId}`, {
    method: "POST",
    schema: NotifyCaseResponseSchema,
  });
}

/**
 * GET /workflow/events
 *
 * Returns workflow audit events ordered newest first. When caseId is
 * provided it is forwarded as the case_id query parameter and only events
 * for that case are returned. When omitted the backend returns the 100 most
 * recent events across all cases.
 */
export async function getWorkflowEvents(
  caseId?: number,
): Promise<WorkflowEvents> {
  const params = new URLSearchParams();

  if (caseId !== undefined) {
    params.set("case_id", String(caseId));
  }

  const query = params.toString();
  const path = `/workflow/events${query ? `?${query}` : ""}`;

  return apiFetch<WorkflowEvents>(path, { schema: WorkflowEventsSchema });
}

/**
 * GET /workflow/stale-cases
 *
 * Returns unreviewed REVIEW/BLOCK cases whose transaction timestamp is
 * older than the given number of minutes. Defaults to 120 minutes when
 * not specified, matching the backend default.
 */
export async function getStaleCases(
  minutes: number = 120,
): Promise<StaleCasesResponse> {
  return apiFetch<StaleCasesResponse>(
    `/workflow/stale-cases?minutes=${minutes}`,
    { schema: StaleCasesResponseSchema },
  );
}

/**
 * GET /workflow/daily-summary
 *
 * Returns an all-time operational summary covering case volume, decision
 * distribution, analyst review status, and workflow event counts.
 */
export async function getDailySummary(): Promise<DailySummary> {
  return apiFetch<DailySummary>("/workflow/daily-summary", {
    schema: DailySummarySchema,
  });
}

/**
 * GET /workflow/metrics
 *
 * Returns workflow automation observability metrics including scalar counts
 * and breakdowns by action, source, and status.
 */
export async function getWorkflowMetrics(): Promise<WorkflowMetrics> {
  return apiFetch<WorkflowMetrics>("/workflow/metrics", {
    schema: WorkflowMetricsSchema,
  });
}
