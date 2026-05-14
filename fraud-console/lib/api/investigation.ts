import { apiFetch } from "@/lib/api/client";
import {
  type InvestigationResponse,
  type TriggerInvestigationResponse,
  InvestigationResponseSchema,
  TriggerInvestigationResponseSchema,
} from "@/types/investigation";

/**
 * GET /cases/{caseId}/investigation
 *
 * Returns the latest investigation state for a case. The response shape
 * varies by status:
 *   202  { status: "IN_PROGRESS" }        — investigation is running
 *   200  { status: "FAILED", ... }        — investigation failed
 *   200  full InvestigationReport row     — investigation complete
 *   404  → thrown as ApiError             — no investigation triggered yet
 *
 * Callers should inspect the returned status field to determine which
 * branch they are in. Hooks that poll this endpoint should stop when
 * status is COMPLETE or FAILED.
 */
export async function getInvestigation(
  caseId: number,
): Promise<InvestigationResponse> {
  return apiFetch<InvestigationResponse>(`/cases/${caseId}/investigation`, {
    schema: InvestigationResponseSchema,
  });
}

/**
 * POST /cases/{id}/investigate
 *
 * Triggers a new agentic investigation for the given case. The backend
 * publishes an InvestigationRequest to Kafka and returns 202 immediately.
 * Poll getInvestigation() to track progress.
 *
 * No request body is required — the case_id is encoded in the URL path.
 */
export async function triggerInvestigation(
  caseId: number,
): Promise<TriggerInvestigationResponse> {
  return apiFetch<TriggerInvestigationResponse>(
    `/cases/${caseId}/investigate`,
    {
      method: "POST",
      schema: TriggerInvestigationResponseSchema,
    },
  );
}
