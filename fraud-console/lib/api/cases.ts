import { apiFetch } from "@/lib/api/client";
import {
  type AnalystStatus,
  type Prediction,
  type ReviewQueue,
  type ReviewRequest,
  type ReviewResponse,
  PredictionSchema,
  ReviewQueueSchema,
  ReviewResponseSchema,
} from "@/types/case";

/**
 * GET /review-queue
 *
 * Returns all REVIEW and BLOCK cases. When analystStatus is provided and
 * non-null it is forwarded as the analyst_status query parameter so the
 * backend applies the filter server-side. Passing null or omitting the
 * argument returns all cases regardless of review state.
 */
export async function getReviewQueue(
  analystStatus?: AnalystStatus,
): Promise<ReviewQueue> {
  const params = new URLSearchParams();

  if (analystStatus !== undefined && analystStatus !== null) {
    params.set("analyst_status", analystStatus);
  }

  const query = params.toString();
  const path = `/review-queue${query ? `?${query}` : ""}`;

  return apiFetch<ReviewQueue>(path, { schema: ReviewQueueSchema });
}

/**
 * GET /case/{caseId}
 *
 * Fetches a single prediction row by primary key.
 * Throws ApiError with status 404 if the case does not exist.
 */
export async function getCase(caseId: number): Promise<Prediction> {
  return apiFetch<Prediction>(`/case/${caseId}`, {
    schema: PredictionSchema,
  });
}

/**
 * POST /review-case/{caseId}
 *
 * Submits an analyst verdict (status + optional notes) for a case.
 * Returns the updated case metadata including the recorded reviewed_at
 * timestamp.
 */
export async function reviewCase(
  caseId: number,
  payload: ReviewRequest,
): Promise<ReviewResponse> {
  return apiFetch<ReviewResponse>(`/review-case/${caseId}`, {
    method: "POST",
    body: payload,
    schema: ReviewResponseSchema,
  });
}
