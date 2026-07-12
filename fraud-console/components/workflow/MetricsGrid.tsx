import { type WorkflowMetrics } from "@/types/workflow";

interface FailureCardProps {
  label: string;
  value: number;
  helper: string;
}

function FailureCard({ label, value, helper }: FailureCardProps) {
  const isAlert = value > 0;
  return (
    <div
      className="card flex flex-col gap-1.5 p-4"
      style={
        isAlert
          ? {
              borderLeft: "3px solid rgba(255,77,77,0.55)",
              background: "linear-gradient(160deg, rgba(255,77,77,0.07) 0%, rgba(20,29,43,0.90) 100%)",
            }
          : {
              borderLeft: "2px solid rgba(16,185,129,0.35)",
              background: "rgba(16,185,129,0.02)",
            }
      }
    >
      <p
        className="text-[32px] font-bold tabular-nums leading-none"
        style={{ color: isAlert ? "#FF4D4D" : "#10B981" }}
      >
        {value}
      </p>
      <p
        className="text-[11px] uppercase tracking-wide"
        style={{ color: isAlert ? "rgba(255,77,77,0.60)" : "rgba(16,185,129,0.55)" }}
      >
        {label}
      </p>
      <p className="text-[11px] leading-snug" style={{ color: "#94A3B8" }}>
        {helper}
      </p>
      <p className="text-[11px] font-semibold" style={{ color: isAlert ? "#FF4D4D" : "#10B981" }}>
        {isAlert ? "Attention required" : "No failures recorded"}
      </p>
    </div>
  );
}

interface PulseCardProps {
  label: string;
  value: number;
  helper: string;
}

function PulseCard({ label, value, helper }: PulseCardProps) {
  return (
    <div className="card flex flex-col gap-1.5 p-3">
      <p className="text-[24px] font-semibold tabular-nums leading-none" style={{ color: "#C9D1D9" }}>
        {value}
      </p>
      <p className="text-[11px] uppercase tracking-wide" style={{ color: "#94A3B8" }}>
        {label}
      </p>
      <p className="text-[11px] leading-snug" style={{ color: "#94A3B8" }}>
        {helper}
      </p>
    </div>
  );
}

interface MetricsGridProps {
  metrics: WorkflowMetrics;
}

export function MetricsGrid({ metrics }: MetricsGridProps) {
  return (
    <div className="space-y-3">
      {/* Failure spotlight */}
      <div className="grid grid-cols-2 gap-3">
        <FailureCard
          label="Failed Events"
          value={metrics.total_failed_events}
          helper="Events that did not complete successfully"
        />
        <FailureCard
          label="Dispatch Failures"
          value={metrics.total_dispatch_failures}
          helper="Workflow handoffs requiring attention"
        />
      </div>
      {/* Pipeline pulse */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <PulseCard
          label="Total Events"
          value={metrics.total_workflow_events}
          helper="All workflow records captured"
        />
        <PulseCard
          label="Automation Events"
          value={metrics.total_n8n_events}
          helper="Events emitted by n8n automation"
        />
        <PulseCard
          label="Inspection Events"
          value={metrics.total_inspection_events}
          helper="Events from the synthetic inspection dataset"
        />
        <PulseCard
          label="Manual Events"
          value={metrics.total_manual_events}
          helper="Operator or analyst-originated events"
        />
        <PulseCard
          label="Escalations"
          value={metrics.total_escalation_events}
          helper="Fraud operations handoff signals"
        />
      </div>
    </div>
  );
}
