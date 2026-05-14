import { z } from "zod";

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const InvestigationStatusSchema = z.enum([
  "IN_PROGRESS",
  "COMPLETE",
  "FAILED",
]);
export type InvestigationStatus = z.infer<typeof InvestigationStatusSchema>;

export const RecommendationSchema = z.enum([
  "CONFIRM_FRAUD",
  "FALSE_POSITIVE",
  "ESCALATE",
]);
export type Recommendation = z.infer<typeof RecommendationSchema>;

export const ConfidenceSchema = z.enum(["HIGH", "MEDIUM", "LOW"]);
export type Confidence = z.infer<typeof ConfidenceSchema>;

// ---------------------------------------------------------------------------
// Full investigation report
// ---------------------------------------------------------------------------

/**
 * JSON text fields may arrive as raw JSON strings or as pre-parsed values
 * depending on the backend serialisation path. Both shapes are accepted.
 */
export const InvestigationReportSchema = z.object({
  id: z.number(),
  investigation_id: z.string(),
  case_id: z.number(),
  agent_version: z.string(),
  investigated_at: z.string(),
  status: InvestigationStatusSchema,
  // Deterministic tool outputs
  transaction_count_30d: z.number().nullable(),
  amount_percentile: z.coerce.number().nullable(),
  merchant_seen_before: z.boolean().nullable(),
  rules_triggered: z
    .union([z.string(), z.array(z.string())])
    .nullable(),
  feature_breakdown: z
    .union([z.string(), z.record(z.string(), z.unknown())])
    .nullable(),
  // LLM outputs
  summary: z.string().nullable(),
  risk_factors: z
    .union([z.string(), z.array(z.string())])
    .nullable(),
  mitigating_factors: z
    .union([z.string(), z.array(z.string())])
    .nullable(),
  recommendation: RecommendationSchema.nullable(),
  recommendation_rationale: z.string().nullable(),
  confidence: ConfidenceSchema.nullable(),
  confidence_rationale: z.string().nullable(),
  // Retrieval provenance
  playbooks_referenced: z
    .union([z.string(), z.array(z.string())])
    .nullable(),
  policies_referenced: z
    .union([z.string(), z.array(z.string())])
    .nullable(),
  // Error state
  error_message: z.string().nullable(),
});
export type InvestigationReport = z.infer<typeof InvestigationReportSchema>;

// ---------------------------------------------------------------------------
// GET /cases/{id}/investigation — union of possible response shapes
// ---------------------------------------------------------------------------

/**
 * The endpoint returns:
 *   202  { status: "IN_PROGRESS" }
 *   200  { status: "FAILED", error_message: string | null }
 *   200  full InvestigationReport row
 *   404  -> thrown as ApiError by apiFetch
 */
export const InProgressResponseSchema = z.object({
  status: z.literal("IN_PROGRESS"),
});
export type InProgressResponse = z.infer<typeof InProgressResponseSchema>;

export const FailedResponseSchema = z.object({
  status: z.literal("FAILED"),
  error_message: z.string().nullable(),
});
export type FailedResponse = z.infer<typeof FailedResponseSchema>;

export const InvestigationResponseSchema = z.union([
  InProgressResponseSchema,
  FailedResponseSchema,
  InvestigationReportSchema,
]);
export type InvestigationResponse = z.infer<typeof InvestigationResponseSchema>;

// ---------------------------------------------------------------------------
// POST /cases/{id}/investigate — response
// ---------------------------------------------------------------------------

export const TriggerInvestigationResponseSchema = z.object({
  status: z.string(),
  investigation_id: z.string(),
  case_id: z.number(),
});
export type TriggerInvestigationResponse = z.infer<
  typeof TriggerInvestigationResponseSchema
>;
