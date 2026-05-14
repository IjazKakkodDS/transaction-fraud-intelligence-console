"use client";

import { useTriggerInvestigation } from "@/lib/hooks/useTriggerInvestigation";

interface InvestigationTriggerProps {
  caseId: number;
  label?: string;
}

export function InvestigationTrigger({
  caseId,
  label = "Run AI Investigation",
}: InvestigationTriggerProps) {
  const { mutate, isPending, isError, error } = useTriggerInvestigation(caseId);

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={() => mutate()}
        disabled={isPending}
        className="inline-flex w-fit items-center gap-2 rounded-md px-4 py-2 text-[13px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-35"
        style={{
          background: "rgba(34,211,238,0.10)",
          border: "1px solid rgba(34,211,238,0.28)",
          color: "#22D3EE",
          minHeight: "38px",
        }}
      >
        {isPending && (
          <span
            className="h-3.5 w-3.5 animate-spin rounded-full border-2"
            style={{ borderColor: "rgba(34,211,238,0.25)", borderTopColor: "#22D3EE" }}
          />
        )}
        {isPending ? "Starting..." : label}
      </button>
      {isError && (
        <p className="text-[13px]" style={{ color: "#FF4D4D" }}>
          {error instanceof Error ? error.message : "Failed to trigger investigation. Try again."}
        </p>
      )}
    </div>
  );
}
