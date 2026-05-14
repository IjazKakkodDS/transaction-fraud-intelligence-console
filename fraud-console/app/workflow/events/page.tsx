"use client";

import { useWorkflowEvents } from "@/lib/hooks/useWorkflowEvents";
import { EventsTable } from "@/components/workflow/EventsTable";
import { type WorkflowEvents } from "@/types/workflow";

function Skeleton() {
  return (
    <div className="card overflow-hidden">
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="h-10 animate-pulse"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.04)", background: "rgba(255,255,255,0.03)" }}
        />
      ))}
    </div>
  );
}

function AuditSummaryRail({ events }: { events: WorkflowEvents }) {
  const total = events.length;
  const successful = events.filter((e) => e.status.toUpperCase() === "SUCCESS").length;
  const failed = events.filter((e) => e.status.toUpperCase() === "FAILED").length;
  const escalations = events.filter((e) => {
    const action = e.workflow_action.toUpperCase();
    return action.includes("ESCALATE") || action.includes("ESCALATION");
  }).length;
  const caseLinked = events.filter((e) => e.case_id !== null).length;

  const stats = [
    { label: "Total Events", value: total,       color: "#C9D1D9" },
    { label: "Successful",   value: successful,  color: "#10B981" },
    { label: "Failed",       value: failed,      color: "#FF4D4D" },
    { label: "Escalations",  value: escalations, color: "#F59E0B" },
    { label: "Case Linked",  value: caseLinked,  color: "#22D3EE" },
  ];

  return (
    <div className="grid grid-cols-5 gap-3">
      {stats.map((s) => (
        <div key={s.label} className="card px-4 py-3">
          <p className="text-[11px] mb-1" style={{ color: "#4B5563" }}>{s.label}</p>
          <p className="text-[22px] font-semibold leading-none" style={{ color: s.color }}>{s.value}</p>
        </div>
      ))}
    </div>
  );
}

function getCoverageLabel(events: WorkflowEvents) {
  const timestamps = events
    .map((event) => new Date(event.created_at).getTime())
    .filter((time) => Number.isFinite(time))
    .sort((a, b) => a - b);

  if (timestamps.length === 0) return null;

  const formatter = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
  });
  const start = formatter.format(new Date(timestamps[0]));
  const end = formatter.format(new Date(timestamps[timestamps.length - 1]));

  return start === end ? `Coverage: ${start}` : `Coverage: ${start} to ${end}`;
}

export default function WorkflowEventsPage() {
  const { data, isLoading, isError } = useWorkflowEvents();
  const coverageLabel = data ? getCoverageLabel(data) : null;

  return (
    <div className="mx-auto max-w-7xl space-y-4 pb-4">
      {/* Hero */}
      <div
        className="border-b pb-4"
        style={{ borderColor: "rgba(255,255,255,0.06)" }}
      >
        <p className="route-label mb-1">Workflow Intelligence</p>
        <h1 className="page-hero-title">
          Audit Trail
          {data && (
            <span className="ml-3 text-[16px] font-normal" style={{ color: "#94A3B8" }}>
              {data.length} {data.length === 1 ? "event" : "events"}
            </span>
          )}
        </h1>
        <p className="text-[13px] leading-relaxed max-w-2xl" style={{ color: "#94A3B8" }}>
          Complete record of automation events emitted by the fraud pipeline. Each event captures
          the action taken, source trigger, and execution status for full auditability.
        </p>
        {coverageLabel && (
          <p className="mt-2 text-[12px] font-medium" style={{ color: "#CBD5E1" }}>
            {coverageLabel}
          </p>
        )}
      </div>

      {data && <AuditSummaryRail events={data} />}

      {isLoading && <Skeleton />}

      {isError && (
        <div
          className="rounded-lg px-4 py-2.5 text-[13px]"
          style={{ background: "rgba(255,77,77,0.07)", border: "1px solid rgba(255,77,77,0.22)", color: "#FF4D4D" }}
        >
          Could not load workflow events. Check API connectivity.
        </div>
      )}

      {data && <EventsTable events={data} />}
    </div>
  );
}
