import { useQuery } from "@tanstack/react-query";
import { fetchRiskScanResults } from "@/lib/api/riskScan";
import { type RiskScanResultsFilters } from "@/types/riskScan";
import { queryKeys } from "@/lib/hooks/queryKeys";

/**
 * Fetches the persisted result rows for a scan with optional filters.
 *
 * The query key includes the filters object so that changing tier, decision,
 * validation_status, or promoted automatically triggers a fresh fetch. The
 * backend sorts results by risk_score DESC NULLS LAST, then row_number ASC.
 *
 * Disabled until scanId is available.
 */
export function useRiskScanResults(
  scanId?: string,
  filters?: RiskScanResultsFilters,
) {
  return useQuery({
    queryKey: queryKeys.riskScanResults(scanId ?? "", filters),
    queryFn: () => fetchRiskScanResults(scanId!, filters),
    enabled: !!scanId,
  });
}