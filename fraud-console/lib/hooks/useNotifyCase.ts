import { useMutation, useQueryClient } from "@tanstack/react-query";
import { notifyCase } from "@/lib/api/workflow";
import { queryKeys } from "@/lib/hooks/queryKeys";

export function useNotifyCase(caseId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => notifyCase(caseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflowEvents(caseId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.workflowMetrics() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dailySummary() });
    },
    onError: () => {
      // The backend writes a WORKFLOW_DISPATCH_FAILED audit event even on 502/503.
      // Invalidate so CaseWorkflowEvents shows the failure record immediately.
      queryClient.invalidateQueries({ queryKey: queryKeys.workflowEvents(caseId) });
    },
  });
}
