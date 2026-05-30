import { useMutation, useQueryClient } from "@tanstack/react-query";
import { promoteRiskScanResult } from "@/lib/api/riskScan";
import { queryKeys } from "@/lib/hooks/queryKeys";

interface PromoteParams {
  scanId: string;
  resultId: number;
}

/**
 * Promotes a stored VALID scan result into the predictions table.
 *
 * On success, invalidates the results and summary queries for the affected
 * scan so the promoted flag and updated counts reflect immediately without
 * a manual page refresh.
 */
export function useRiskScanPromote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ scanId, resultId }: PromoteParams) =>
      promoteRiskScanResult(scanId, resultId),
    onSuccess: (_, { scanId }) => {
      // Prefix-based invalidation clears all filter variants for this scan.
      queryClient.invalidateQueries({
        queryKey: queryKeys.riskScanResults(scanId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.riskScanSummary(scanId),
      });
    },
  });
}