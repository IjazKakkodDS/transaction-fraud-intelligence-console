import { useQuery } from "@tanstack/react-query";
import { getCaseExplanation } from "@/lib/api/explain";
import { queryKeys } from "@/lib/hooks/queryKeys";

export function useCaseExplanation(caseId: number) {
  return useQuery({
    queryKey: queryKeys.caseExplanation(caseId),
    queryFn: () => getCaseExplanation(caseId),
    enabled: caseId > 0,
    retry: false,
  });
}
