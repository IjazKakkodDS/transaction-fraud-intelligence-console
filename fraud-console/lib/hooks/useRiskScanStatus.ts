import { useQuery } from "@tanstack/react-query";
import { fetchRiskScanStatus } from "@/lib/api/riskScan";
import { type RiskScanStatus } from "@/types/riskScan";
import { queryKeys } from "@/lib/hooks/queryKeys";

const ACTIVE_STATUSES = new Set(["QUEUED", "PROCESSING"]);

export function useRiskScanStatus(scanId?: string) {
  return useQuery({
    queryKey: queryKeys.riskScanStatus(scanId ?? ""),
    queryFn: () => fetchRiskScanStatus(scanId!),
    enabled: !!scanId,
    refetchInterval: (query) => {
      const status = (query.state.data as RiskScanStatus | undefined)?.status;
      return status && ACTIVE_STATUSES.has(status) ? 1000 : false;
    },
  });
}
