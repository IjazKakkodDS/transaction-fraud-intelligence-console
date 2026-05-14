import { useQuery } from "@tanstack/react-query";
import { getWorkflowEvents } from "@/lib/api/workflow";
import { queryKeys } from "@/lib/hooks/queryKeys";

export function useWorkflowEvents(caseId?: number) {
  return useQuery({
    queryKey: queryKeys.workflowEvents(caseId),
    queryFn: () => getWorkflowEvents(caseId),
  });
}
