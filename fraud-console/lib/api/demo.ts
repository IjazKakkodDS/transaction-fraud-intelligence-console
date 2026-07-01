import { apiFetch } from "@/lib/api/client";

export interface DemoSeedResponse {
  status: "seeded" | "already_exists";
  message: string;
  case_id: number | null;
  case_url: string | null;
  recommended_flow: string[];
  cases: {
    showcase: {
      case_id: number | null;
      decision: string | null;
      risk_score: number | null;
      description: string;
    };
    review: {
      case_id: number | null;
      decision: string | null;
      analyst_status: string;
      description: string;
    };
  };
}

export async function seedDemoState(): Promise<DemoSeedResponse> {
  return apiFetch<DemoSeedResponse>("/cases/seed-review", { method: "POST" });
}
