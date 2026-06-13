import { apiFetch } from "@/lib/api/client";

export interface FeatureContribution {
  feature: string;
  value: number;
  contribution_logit: number;
  direction: "increases_risk" | "decreases_risk" | "neutral";
  rank: number;
}

export interface CaseExplanation {
  case_id: number;
  model_type: string;
  explanation_method: string;
  bias_logit: number;
  features: FeatureContribution[];
  top_positive: FeatureContribution[];
  top_negative: FeatureContribution[];
  reconstructed_features: Record<string, number>;
  inferred_fields: string[];
  notes: string[];
}

export async function getCaseExplanation(caseId: number): Promise<CaseExplanation> {
  return apiFetch<CaseExplanation>(`/cases/${caseId}/explain`);
}
