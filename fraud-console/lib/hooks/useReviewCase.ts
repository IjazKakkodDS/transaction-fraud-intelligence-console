import { useMutation, useQueryClient } from "@tanstack/react-query";
import { reviewCase } from "@/lib/api/cases";
import { type ReviewRequest } from "@/types/case";
import { queryKeys } from "@/lib/hooks/queryKeys";

export function useReviewCase(caseId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: ReviewRequest) => reviewCase(caseId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.case(caseId) });
      queryClient.invalidateQueries({ queryKey: ["reviewQueue"] });
    },
  });
}
