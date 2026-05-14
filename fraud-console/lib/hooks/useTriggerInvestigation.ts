import { useMutation, useQueryClient } from "@tanstack/react-query";
import { triggerInvestigation } from "@/lib/api/investigation";
import { queryKeys } from "@/lib/hooks/queryKeys";

export function useTriggerInvestigation(caseId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => triggerInvestigation(caseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.investigation(caseId) });
    },
  });
}
