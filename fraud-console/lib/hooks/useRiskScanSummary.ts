import { useQuery } from "@tanstack/react-query";
import { fetchRiskScanSummary } from "@/lib/api/riskScan";
import { queryKeys } from "@/lib/hooks/queryKeys";

/**
 * Fetches the full scan summary for a completed scan.
 * Disabled until scanId is available so components can mount before an
 * upload has been submitted.
 */
export function useRiskScanSummary(scanId?: string) {
  return useQuery({
    queryKey: queryKeys.riskScanSummary(scanId ?? ""),
    queryFn: () => fetchRiskScanSummary(scanId!),
    enabled: !!scanId,
  });
}