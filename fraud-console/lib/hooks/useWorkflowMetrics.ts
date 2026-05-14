import { useQuery } from "@tanstack/react-query";
import { getWorkflowMetrics } from "@/lib/api/workflow";
import { queryKeys } from "@/lib/hooks/queryKeys";

export function useWorkflowMetrics() {
  return useQuery({
    queryKey: queryKeys.workflowMetrics(),
    queryFn: getWorkflowMetrics,
    refetchInterval: 60_000,
  });
}
