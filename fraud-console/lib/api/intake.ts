import { apiFetch } from "@/lib/api/client";
import { ApiError } from "@/types/api";
import { PredictionSchema, type Prediction } from "@/types/case";
import { type IntakePayload } from "@/types/intake";

export async function submitTransaction(payload: IntakePayload): Promise<void> {
  await apiFetch<unknown>("/predict", {
    method: "POST",
    body: payload,
  });
}

export async function fetchScoredTransaction(
  transactionId: string,
): Promise<Prediction | null> {
  try {
    return await apiFetch<Prediction>(`/predictions/${transactionId}`, {
      schema: PredictionSchema,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}
