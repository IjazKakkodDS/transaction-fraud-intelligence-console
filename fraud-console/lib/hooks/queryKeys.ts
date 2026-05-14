/**
 * Centralized TanStack Query key factory.
 *
 * All query keys are defined here so that invalidation calls in mutation
 * hooks stay in sync with the keys used in query hooks. Using array keys
 * enables prefix-based invalidation — e.g. invalidating ["reviewQueue"]
 * clears every filtered variant automatically.
 */

export const queryKeys = {
  reviewQueue: (analystStatus?: string | null) =>
    ["reviewQueue", analystStatus] as const,

  case: (caseId: number) =>
    ["case", caseId] as const,

  investigation: (caseId: number) =>
    ["investigation", caseId] as const,

  workflowEvents: (caseId?: number) =>
    ["workflowEvents", caseId] as const,

  staleCases: (minutes: number) =>
    ["staleCases", minutes] as const,

  dailySummary: () =>
    ["dailySummary"] as const,

  workflowMetrics: () =>
    ["workflowMetrics"] as const,
} as const;
