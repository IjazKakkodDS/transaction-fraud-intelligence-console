import { useQuery } from "@tanstack/react-query";
import { getCase } from "@/lib/api/cases";
import { queryKeys } from "@/lib/hooks/queryKeys";

/**
 * Fetches a single prediction row by primary key.
 * The query is disabled when caseId is 0 or negative to prevent
 * accidental requests before a valid ID is available.
 */
export function useCase(caseId: number) {
  return useQuery({
    queryKey: queryKeys.case(caseId),
    queryFn: () => getCase(caseId),
    enabled: caseId > 0,
  });
}
