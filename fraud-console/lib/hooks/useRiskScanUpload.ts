import { useMutation } from "@tanstack/react-query";
import { uploadRiskScan } from "@/lib/api/riskScan";

/**
 * Wraps uploadRiskScan(file) as a mutation.
 *
 * The caller is responsible for handling the returned scan_id — typically
 * storing it in local state to drive subsequent summary/results queries.
 * No automatic query invalidation is needed here because no "scan list"
 * query exists yet; invalidation will be added when the list view is built.
 */
export function useRiskScanUpload() {
  return useMutation({
    mutationFn: (file: File) => uploadRiskScan(file),
  });
}