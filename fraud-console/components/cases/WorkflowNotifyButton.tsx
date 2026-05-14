"use client";

import { useState } from "react";
import { useNotifyCase } from "@/lib/hooks/useNotifyCase";
import { sanitizeWorkflowMessage } from "@/lib/utils";

interface WorkflowNotifyButtonProps {
  caseId: number;
}

export function WorkflowNotifyButton({ caseId }: WorkflowNotifyButtonProps) {
  const [dispatched, setDispatched] = useState(false);
  const { mutate, isPending, isError, error } = useNotifyCase(caseId);

  function handleClick() {
    setDispatched(false);
    mutate(undefined, { onSuccess: () => setDispatched(true) });
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={handleClick}
        disabled={isPending}
        className="inline-flex w-fit items-center gap-2 rounded-md px-4 py-2.5 text-[13px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-35"
        style={{
          background: "rgba(255,255,255,0.05)",
          border: "1px solid rgba(255,255,255,0.10)",
          color: "#C9D1D9",
          minHeight: "40px",
        }}
      >
        {isPending && (
          <span
            className="h-3.5 w-3.5 animate-spin rounded-full border-2"
            style={{ borderColor: "rgba(201,209,217,0.20)", borderTopColor: "#C9D1D9" }}
          />
        )}
        {isPending ? "Dispatching..." : "Dispatch Workflow Automation"}
      </button>
      {dispatched && (
        <p className="text-[13px] font-medium" style={{ color: "#10B981" }}>
          Workflow automation dispatched.
        </p>
      )}
      {isError && (
        <p className="text-[13px]" style={{ color: "#FF4D4D" }}>
          {error instanceof Error
            ? sanitizeWorkflowMessage(error.message)
            : "Could not dispatch workflow automation. Check API connectivity."}
        </p>
      )}
    </div>
  );
}
