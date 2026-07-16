import { z } from "zod";
import { PredictionSchema } from "@/types/case";

// ---------------------------------------------------------------------------
// Workflow event row
// ---------------------------------------------------------------------------

/**
 * case_id is nullable — global events (e.g. DAILY_FRAUD_OPS_SUMMARY) have
 * no associated prediction row.
 * payload arrives as either a JSON string or a parsed object depending on
 * whether the n8n or FastAPI caller serialised it before sending.
 */
export const WorkflowEventSchema = z.object({
  id: z.number(),
  case_id: z.number().nullable(),
  workflow_name: z.string(),
  workflow_action: z.string(),
  status: z.string(),
  escalation_priority: z.string().nullable(),
  message: z.string().nullable(),
  payload: z
    .union([z.string(), z.record(z.string(), z.unknown())])
    .nullable(),
  source: z.string(),
  created_at: z.string(),
});
export type WorkflowEvent = z.infer<typeof WorkflowEventSchema>;

export const WorkflowEventsSchema = z.array(WorkflowEventSchema);
export type WorkflowEvents = z.infer<typeof WorkflowEventsSchema>;

// ---------------------------------------------------------------------------
// GET /workflow/stale-cases
// ---------------------------------------------------------------------------

export const StaleCasesResponseSchema = z.object({
  minutes: z.number(),
  count: z.number(),
  cases: z.array(PredictionSchema),
});
export type StaleCasesResponse = z.infer<typeof StaleCasesResponseSchema>;

// ---------------------------------------------------------------------------
// GET /workflow/daily-summary
// ---------------------------------------------------------------------------

export const DailySummarySchema = z.object({
  window: z.string(),
  generated_at: z.string(),
  total_cases: z.number(),
  total_review: z.number(),
  total_block: z.number(),
  total_approve: z.number(),
  unreviewed_cases: z.number(),
  confirmed_fraud: z.number(),
  false_positive: z.number(),
  average_risk_score: z.number(),
  total_workflow_events: z.number(),
  automation_escalation_events: z.number(),
  total_stale_reminders: z.number(),
  latest_workflow_event_at: z.string().nullable(),
});
export type DailySummary = z.infer<typeof DailySummarySchema>;

// ---------------------------------------------------------------------------
// GET /workflow/metrics — breakdown item shapes
// ---------------------------------------------------------------------------

export const ActionBreakdownItemSchema = z.object({
  workflow_action: z.string(),
  count: z.number(),
});
export type ActionBreakdownItem = z.infer<typeof ActionBreakdownItemSchema>;

export const SourceBreakdownItemSchema = z.object({
  source: z.string(),
  count: z.number(),
});
export type SourceBreakdownItem = z.infer<typeof SourceBreakdownItemSchema>;

export const StatusBreakdownItemSchema = z.object({
  status: z.string(),
  count: z.number(),
});
export type StatusBreakdownItem = z.infer<typeof StatusBreakdownItemSchema>;

export const WorkflowMetricsSchema = z.object({
  generated_at: z.string(),
  total_workflow_events: z.number(),
  total_success_events: z.number(),
  total_failed_events: z.number(),
  total_n8n_events: z.number(),
  total_manual_events: z.number(),
  total_inspection_events: z.number(),
  total_case_specific_events: z.number(),
  total_global_events: z.number(),
  total_escalation_events: z.number(),
  total_stale_reminders: z.number(),
  total_daily_summaries: z.number(),
  total_dispatch_failures: z.number(),
  latest_workflow_event_at: z.string().nullable(),
  events_by_workflow_action: z.array(ActionBreakdownItemSchema),
  events_by_source: z.array(SourceBreakdownItemSchema),
  events_by_status: z.array(StatusBreakdownItemSchema),
});
export type WorkflowMetrics = z.infer<typeof WorkflowMetricsSchema>;

// ---------------------------------------------------------------------------
// POST /workflow/notify-case/{case_id}
// ---------------------------------------------------------------------------

export const NotifyCaseResponseSchema = z.object({
  status: z.string(),
  case_id: z.number(),
  workflow_url: z.string(),
});
export type NotifyCaseResponse = z.infer<typeof NotifyCaseResponseSchema>;
