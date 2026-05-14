import { useQuery } from "@tanstack/react-query";
import { getStaleCases } from "@/lib/api/workflow";
import { queryKeys } from "@/lib/hooks/queryKeys";

export function useStaleCases(minutes: number = 120) {
  return useQuery({
    queryKey: queryKeys.staleCases(minutes),
    queryFn: () => getStaleCases(minutes),
    refetchInterval: 60_000,
  });
}
