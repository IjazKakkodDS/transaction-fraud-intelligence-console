import { z } from "zod";

export const RiskScanJobStatusSchema = z.enum([
  "QUEUED",
  "PROCESSING",
  "COMPLETE",
  "FAILED",
  "CANCELLED",
]);
export type RiskScanJobStatus = z.infer<typeof RiskScanJobStatusSchema>;

// ---------------------------------------------------------------------------
// POST /risk-scan/upload — response
// ---------------------------------------------------------------------------

export const RiskScanUploadResponseSchema = z.object({
  scan_id: z.string(),
  status: RiskScanJobStatusSchema,
  total_rows: z.number(),
});
export type RiskScanUploadResponse = z.infer<typeof RiskScanUploadResponseSchema>;

// ---------------------------------------------------------------------------
// GET /risk-scan/{scan_id}/status
// ---------------------------------------------------------------------------

export const RiskScanStatusSchema = z.object({
  scan_id: z.string(),
  status: RiskScanJobStatusSchema,
  total_rows: z.number(),
  processed_rows: z.number(),
  progress_percent: z.number(),
  valid_rows: z.number(),
  invalid_rows: z.number(),
  skipped_rows: z.number(),
  p0_count: z.number(),
  p1_count: z.number(),
  p2_count: z.number(),
  p3_count: z.number(),
  created_at: z.string().nullable().optional(),
  started_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
  cancelled_at: z.string().nullable().optional(),
  error_message: z.string().nullable().optional(),
});
export type RiskScanStatus = z.infer<typeof RiskScanStatusSchema>;

// ---------------------------------------------------------------------------
// GET /risk-scan/{scan_id}/summary
// ---------------------------------------------------------------------------

export const RiskScanSummarySchema = z.object({
  scan_id: z.string(),
  status: z.string(),
  filename: z.string().nullable(),
  total_rows: z.number(),
  valid_rows: z.number(),
  invalid_rows: z.number(),
  skipped_rows: z.number(),
  tier_distribution: z.object({
    critical: z.number(),
    high: z.number(),
    medium: z.number(),
    low: z.number(),
  }),
  priority_distribution: z.object({
    p0: z.number(),
    p1: z.number(),
    p2: z.number(),
    p3: z.number(),
  }),
  exposure: z.object({
    total_amount: z.number(),
    critical_amount: z.number(),
    high_amount: z.number(),
  }),
  // Flexible catch-all: the backend shape contains nested objects with
  // {reason,count}, {country,count} etc. We validate loosely so the type
  // system does not break when new keys are added.
  risk_summary: z.record(z.string(), z.unknown()).nullable(),
  created_at: z.string().nullable(),
  completed_at: z.string().nullable(),
});
export type RiskScanSummary = z.infer<typeof RiskScanSummarySchema>;

// ---------------------------------------------------------------------------
// GET /risk-scan/{scan_id}/results — individual result row
// ---------------------------------------------------------------------------

export const RiskScanResultSchema = z.object({
  id: z.number(),
  scan_id: z.string().optional(),
  row_number: z.number(),
  transaction_id: z.string().nullable(),
  // Use coerce.number() — backend serialises Postgres NUMERIC as a string in
  // some SQLAlchemy configurations; coerce handles both cases transparently.
  amount: z.coerce.number().nullable(),
  timestamp: z.string().nullable(),
  country: z.string().nullable(),
  payment_method: z.string().nullable(),
  merchant_category: z.string().nullable(),
  device_id: z.string().nullable(),
  rule_flag: z.number().nullable(),
  model_prediction: z.number().nullable(),
  risk_score: z.coerce.number().nullable(),
  decision: z.enum(["APPROVE", "REVIEW", "BLOCK"]).nullable(),
  risk_tier: z.enum(["Low", "Medium", "High", "Critical"]).nullable(),
  operational_priority: z.enum(["P0", "P1", "P2", "P3"]).nullable(),
  reasons: z.string().nullable(),
  validation_status: z.enum(["VALID", "INVALID", "SKIPPED"]),
  validation_errors: z.array(z.string()).nullable(),
  promoted: z.boolean(),
  promoted_case_id: z.number().nullable(),
  promoted_at: z.string().nullable(),
});
export type RiskScanResult = z.infer<typeof RiskScanResultSchema>;

export const RiskScanResultsSchema = z.array(RiskScanResultSchema);
export type RiskScanResults = z.infer<typeof RiskScanResultsSchema>;

export const RiskScanPaginatedResultsSchema = z.object({
  items: z.array(RiskScanResultSchema),
  page: z.number(),
  page_size: z.number(),
  total_items: z.number(),
  total_pages: z.number(),
});
export type RiskScanPaginatedResults = z.infer<
  typeof RiskScanPaginatedResultsSchema
>;

// ---------------------------------------------------------------------------
// POST /risk-scan/{scan_id}/promote/{result_id} — response
// ---------------------------------------------------------------------------

export const RiskScanPromoteResponseSchema = z.object({
  case_id: z.number(),
  transaction_id: z.string(),
  promoted_at: z.string(),
  case_dossier_path: z.string(),
});
export type RiskScanPromoteResponse = z.infer<typeof RiskScanPromoteResponseSchema>;

// ---------------------------------------------------------------------------
// Filter params for GET /risk-scan/{scan_id}/results
// Plain TypeScript interface — used as a function argument, not a response.
// ---------------------------------------------------------------------------

export interface RiskScanResultsFilters {
  tier?: "P0" | "P1" | "P2" | "P3";
  decision?: "APPROVE" | "REVIEW" | "BLOCK";
  validation_status?: "VALID" | "INVALID" | "SKIPPED";
  promoted?: boolean;
}

// ---------------------------------------------------------------------------
// GET /risk-scan/recent — scan header list (no result rows)
// ---------------------------------------------------------------------------

export const RecentScanSchema = z.object({
  scan_id: z.string(),
  filename: z.string().nullable(),
  status: RiskScanJobStatusSchema,
  created_at: z.string().nullable().optional(),
  started_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
  processed_rows: z.number(),
  total_rows: z.number(),
  valid_rows: z.number(),
  invalid_rows: z.number(),
  skipped_rows: z.number(),
  p0_count: z.number(),
  p1_count: z.number(),
  p2_count: z.number(),
  p3_count: z.number(),
  total_amount: z.number(),
  critical_amount: z.number(),
  high_amount: z.number(),
  error_message: z.string().nullable().optional(),
});
export type RecentScan = z.infer<typeof RecentScanSchema>;
export const RecentScanListSchema = z.array(RecentScanSchema);
