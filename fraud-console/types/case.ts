import { z } from "zod";

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const DecisionSchema = z.enum(["APPROVE", "REVIEW", "BLOCK"]);
export type Decision = z.infer<typeof DecisionSchema>;

/**
 * UNREVIEWED is not stored in the DB (those rows have analyst_status = NULL).
 * It appears as a filter query parameter value and as a display label.
 * Responses from /case and /review-queue use null for unreviewed rows.
 */
export const AnalystStatusSchema = z
  .enum(["CONFIRMED_FRAUD", "FALSE_POSITIVE", "APPROVED", "UNREVIEWED"])
  .nullable();
export type AnalystStatus = z.infer<typeof AnalystStatusSchema>;

// ---------------------------------------------------------------------------
// Prediction row
// ---------------------------------------------------------------------------

/**
 * Matches the predictions table.
 * event_id is optional — /review-queue omits it; /case/{id} includes it.
 * amount and risk_score use coerce.number() to handle Decimal serialisation
 * differences across SQLAlchemy versions.
 * reasons is stored as a pipe-delimited string ("High amount|Night tx").
 */
export const PredictionSchema = z.object({
  id: z.number(),
  event_id: z.string().nullable().optional(),
  transaction_id: z.string().nullable(),
  amount: z.coerce.number().nullable(),
  timestamp: z.string().nullable(),
  rule_flag: z.number().nullable(),
  model_prediction: z.number().nullable(),
  risk_score: z.coerce.number().nullable(),
  decision: DecisionSchema.nullable(),
  reasons: z.string().nullable(),
  analyst_status: AnalystStatusSchema,
  analyst_notes: z.string().nullable(),
  reviewed_at: z.string().nullable(),
});
export type Prediction = z.infer<typeof PredictionSchema>;

// ---------------------------------------------------------------------------
// Review queue
// ---------------------------------------------------------------------------

export const ReviewQueueSchema = z.array(PredictionSchema);
export type ReviewQueue = z.infer<typeof ReviewQueueSchema>;

// ---------------------------------------------------------------------------
// POST /review-case/{case_id} — request and response
// ---------------------------------------------------------------------------

export const ReviewRequestSchema = z.object({
  analyst_status: z.enum(["CONFIRMED_FRAUD", "FALSE_POSITIVE", "APPROVED"]),
  analyst_notes: z.string().nullable().optional(),
});
export type ReviewRequest = z.infer<typeof ReviewRequestSchema>;

export const ReviewResponseSchema = z.object({
  message: z.string(),
  case_id: z.number(),
  analyst_status: z.string(),
  reviewed_at: z.string(),
});
export type ReviewResponse = z.infer<typeof ReviewResponseSchema>;
