import { useQuery } from "@tanstack/react-query";
import { getInvestigation } from "@/lib/api/investigation";
import { type InvestigationResponse } from "@/types/investigation";
import { ApiError } from "@/types/api";
import { queryKeys } from "@/lib/hooks/queryKeys";

const POLL_MS = 3000;

export function useInvestigation(
  caseId: number,
  pollingUntil: number | null = null,
) {
  return useQuery({
    queryKey: queryKeys.investigation(caseId),
    queryFn: async (): Promise<InvestigationResponse | null> => {
      try {
        return await getInvestigation(caseId);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
    enabled: caseId > 0,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && "status" in data && data.status === "IN_PROGRESS") return POLL_MS;
      // Keep polling while the post-trigger window is open and no result yet.
      if (data === null && pollingUntil !== null && Date.now() < pollingUntil) return POLL_MS;
      return false;
    },
  });
}
