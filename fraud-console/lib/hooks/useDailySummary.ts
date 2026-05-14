import { useQuery } from "@tanstack/react-query";
import { getDailySummary } from "@/lib/api/workflow";
import { queryKeys } from "@/lib/hooks/queryKeys";

export function useDailySummary() {
  return useQuery({
    queryKey: queryKeys.dailySummary(),
    queryFn: getDailySummary,
    refetchInterval: 60_000,
  });
}
