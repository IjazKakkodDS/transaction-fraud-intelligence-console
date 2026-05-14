import { useQuery } from "@tanstack/react-query";
import { getReviewQueue } from "@/lib/api/cases";
import { type AnalystStatus } from "@/types/case";
import { queryKeys } from "@/lib/hooks/queryKeys";

/**
 * Fetches the REVIEW and BLOCK case queue, optionally filtered by analyst
 * status. Refetches every 30 seconds so the queue stays current without
 * requiring a manual page refresh.
 */
export function useReviewQueue(analystStatus?: AnalystStatus) {
  return useQuery({
    queryKey: queryKeys.reviewQueue(analystStatus),
    queryFn: () => getReviewQueue(analystStatus),
    refetchInterval: 30_000,
  });
}
