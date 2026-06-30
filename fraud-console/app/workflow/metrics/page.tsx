"use client";

import { useWorkflowMetrics } from "@/lib/hooks/useWorkflowMetrics";
import { MetricsGrid } from "@/components/workflow/MetricsGrid";
import { ActionBreakdownChart } from "@/components/workflow/ActionBreakdownChart";
import { SourceBreakdownChart } from "@/components/workflow/SourceBreakdownChart";
import { StatusBreakdownChart } from "@/components/workflow/StatusBreakdownChart";
import { formatDateShort } from "@/lib/utils";
import { type WorkflowMetrics } from "@/types/workflow";

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={`rounded-xl animate-pulse ${className ?? ""}`}
      style={{ background: "rgba(255,255,255,0.04)" }}
    />
  );
}

type HealthVerdict = "Healthy" | "Degraded" | "Critical";

function getHealthVerdict(successRate: number, dispatchFailures: number): HealthVerdict {
  if (successRate < 70 || dispatchFailures > 3) return "Critical";
  if (successRate < 90 || dispatchFailures > 0) return "Degraded";
  return "Healthy";
}

const HEALTH_CONFIG: Record<
  HealthVerdict,
  { dot: string; labelColor: string; message: string; card: React.CSSProperties }
> = {
  Healthy: {
    dot: "#10B981",
    labelColor: "#10B981",
    message: "Automation operating within expected limits.",
    card: {
      border: "1px solid rgba(16,185,129,0.22)",
      background: "rgba(16,185,129,0.04)",
    },
  },
  Degraded: {
    dot: "#F59E0B",
    labelColor: "#F59E0B",
    message: "Automation requires monitoring due to failures or reduced success rate.",
    card: {
      border: "1px solid rgba(245,158,11,0.22)",
      background: "rgba(245,158,11,0.04)",
    },
  },
  Critical: {
    dot: "#FF4D4D",
    labelColor: "#FF4D4D",
    message: "Automation reliability requires immediate attention.",
    card: {
      border: "1px solid rgba(255,77,77,0.28)",
      background: "rgba(255,77,77,0.05)",
    },
  },
};

function fmtRate(numerator: number, total: number): string {
  if (total === 0) return "No data";
  return `${((numerator / total) * 100).toFixed(1)}%`;
}

function ReliabilityStatusStrip({ metrics }: { metrics: WorkflowMetrics }) {
  const total = metrics.total_workflow_events;
  const successRate = total > 0 ? (metrics.total_success_events / total) * 100 : 0;
  const verdict = getHealthVerdict(successRate, metrics.total_dispatch_failures);
  const cfg = HEALTH_CONFIG[verdict];

  const rates = [
    { label: "Success Rate",          value: fmtRate(metrics.total_success_events,   total) },
    { label: "Failure Rate",          value: fmtRate(metrics.total_failed_events,    total) },
    { label: "Dispatch Failure Rate", value: fmtRate(metrics.total_dispatch_failures, total) },
    { label: "Automation Coverage",   value: fmtRate(metrics.total_n8n_events,       total) },
  ];

  return (
    <div className="rounded-xl px-5 py-4" style={cfg.card}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span
            className="mt-[3px] inline-block h-2.5 w-2.5 flex-shrink-0 rounded-full"
            style={{ background: cfg.dot, boxShadow: `0 0 6px ${cfg.dot}` }}
          />
          <div>
            <p className="text-[14px] font-semibold leading-none mb-1" style={{ color: cfg.labelColor }}>
              {verdict}
            </p>
            <p className="text-[12px] leading-relaxed" style={{ color: "#94A3B8" }}>
              {cfg.message}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-6">
          {rates.map((r) => (
            <div key={r.label} className="text-right">
              <p className="text-[17px] font-semibold tabular-nums leading-none" style={{ color: "#C9D1D9" }}>
                {r.value}
              </p>
              <p className="mt-0.5 text-[11px]" style={{ color: "#94A3B8" }}>{r.label}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function HostedProfileNote() {
  return (
    <div
      className="rounded-lg px-4 py-3 text-[12px] leading-relaxed"
      style={{ background: "rgba(34,211,238,0.04)", border: "1px solid rgba(34,211,238,0.14)", color: "#94A3B8" }}
    >
      <p className="mb-1 font-semibold" style={{ color: "#C9D1D9" }}>
        No workflow automation events have been recorded in this hosted profile.
      </p>
      <p>
        Reliability metrics populate when workflow automation is enabled in the local
        full-stack runtime. The hosted inspection environment keeps this view available
        for reviewer inspection while external automation is intentionally excluded.
      </p>
    </div>
  );
}

function formatActionName(action: string): string {
  return action
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/^\w/, (c) => c.toUpperCase());
}

function OperationalDiagnosis({ metrics }: { metrics: WorkflowMetrics }) {
  const total = metrics.total_workflow_events;
  const failed = metrics.total_failed_events;
  const dispatchFailures = metrics.total_dispatch_failures;
  const successRate = total > 0 ? (metrics.total_success_events / total) * 100 : 0;
  const failureRate = total > 0 ? (failed / total) * 100 : 0;
  const dispatchFailureRate = total > 0 ? (dispatchFailures / total) * 100 : 0;
  const verdict = getHealthVerdict(successRate, dispatchFailures);
  const topFailingAction = [...metrics.events_by_workflow_action]
    .filter((item) => item.workflow_action.toUpperCase().includes("FAILED"))
    .sort((a, b) => b.count - a.count)[0];
  const latestEvent = metrics.latest_workflow_event_at
    ? formatDateShort(metrics.latest_workflow_event_at)
    : "No events recorded";
  const hasFailures = failed > 0 || dispatchFailures > 0;

  const diagnosis =
    total === 0
      ? "No workflow events have been recorded yet, so automation reliability cannot be assessed."
      : !hasFailures
      ? `Automation reliability is healthy with ${successRate.toFixed(1)}% of workflow events completing successfully.`
      : verdict === "Critical"
      ? `Automation reliability is currently critical because dispatch failures represent ${dispatchFailureRate.toFixed(1)}% of recorded workflow events.`
      : `Automation reliability is degraded with ${failureRate.toFixed(1)}% of workflow events failing.`;
  const impact =
    total === 0
      ? "Workflow telemetry will become meaningful once dispatch and escalation activity is recorded."
      : !hasFailures
      ? "Escalation workflows are active and current automation signals are completing as expected."
      : "Escalation workflows are active, but failed dispatches may delay downstream fraud operations handoff.";
  const recommendation =
    total === 0
      ? "Generate workflow activity before treating reliability metrics as operational evidence."
      : !hasFailures
      ? "Continue monitoring workflow events and audit evidence for drift in automation health."
      : verdict === "Critical"
      ? "Review failed dispatch events in the Audit Trail before treating workflow automation as production-ready."
      : "Review recent failed workflow events and confirm escalation handoffs are reaching the intended destination.";
  const stats = [
    { label: "Latest Event", value: latestEvent },
    { label: "Top Failing Action", value: topFailingAction ? formatActionName(topFailingAction.workflow_action) : "None recorded" },
    { label: "Failure Rate", value: fmtRate(failed, total) },
  ];

  return (
    <div className="card overflow-hidden">
      <div className="grid grid-cols-1 lg:grid-cols-3">
        {[
          { label: "Diagnosis", text: diagnosis },
          { label: "Reliability Impact", text: impact },
          { label: "Recommended Action", text: recommendation },
        ].map((section) => (
          <div
            key={section.label}
            className="min-w-0 px-5 py-4"
            style={{ borderRight: "1px solid rgba(148,163,184,0.10)" }}
          >
            <p className="section-label">{section.label}</p>
            <p className="mt-2 text-[13px] leading-relaxed" style={{ color: "#CBD5E1" }}>
              {section.text}
            </p>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3" style={{ borderTop: "1px solid rgba(148,163,184,0.10)" }}>
        {stats.map((stat) => (
          <div key={stat.label} className="px-5 py-3" style={{ borderRight: "1px solid rgba(148,163,184,0.08)" }}>
            <p className="text-[12px] font-semibold" style={{ color: "#CBD5E1" }}>
              {stat.value}
            </p>
            <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em]" style={{ color: "#94A3B8" }}>
              {stat.label}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ReliabilityTargetPanel({ metrics }: { metrics: WorkflowMetrics }) {
  const total = metrics.total_workflow_events;
  const successRate = total > 0 ? (metrics.total_success_events / total) * 100 : 0;
  const failureRate = total > 0 ? (metrics.total_failed_events / total) * 100 : 0;
  const dispatchFailureRate = total > 0 ? (metrics.total_dispatch_failures / total) * 100 : 0;
  const automationCoverage = total > 0 ? (metrics.total_n8n_events / total) * 100 : 0;
  const targets = [
    {
      label: "Success Rate",
      target: "90%+",
      current: successRate,
      status: successRate >= 90 ? "On Target" : "Below Target",
      good: successRate >= 90,
      color: successRate >= 90 ? "#10B981" : "#F59E0B",
    },
    {
      label: "Dispatch Failure Rate",
      target: "0%",
      current: dispatchFailureRate,
      status: dispatchFailureRate === 0 ? "Clean" : "Needs Attention",
      good: dispatchFailureRate === 0,
      color: dispatchFailureRate === 0 ? "#10B981" : "#FF4D4D",
    },
    {
      label: "Automation Coverage",
      target: "70%+",
      current: automationCoverage,
      status: automationCoverage >= 70 ? "Strong" : "Limited",
      good: automationCoverage >= 70,
      color: automationCoverage >= 70 ? "#10B981" : "#F59E0B",
    },
  ];

  return (
    <div className="card p-5">
      <div className="mb-4">
        <p className="section-label">Reliability Targets</p>
        <p className="mt-1 text-[12px]" style={{ color: "#94A3B8" }}>
          Reliability target tracking for workflow automation health.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        {targets.map((target) => (
          <div
            key={target.label}
            className="rounded-md px-3 py-3"
            style={{
              background: "rgba(255,255,255,0.025)",
              border: `1px solid ${target.good ? "rgba(16,185,129,0.16)" : "rgba(245,158,11,0.18)"}`,
            }}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[12px] font-semibold" style={{ color: "#CBD5E1" }}>
                  {target.label}
                </p>
                <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em]" style={{ color: "#94A3B8" }}>
                  Target: {target.target}
                </p>
              </div>
              <span className="text-[11px] font-semibold" style={{ color: target.color }}>
                {target.status}
              </span>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full" style={{ background: "rgba(148,163,184,0.14)" }}>
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.min(100, Math.max(0, target.current))}%`,
                    background: target.color,
                    opacity: 0.82,
                  }}
                />
              </div>
              <span className="w-12 text-right text-[12px] font-semibold tabular-nums" style={{ color: "#CBD5E1" }}>
                {target.current.toFixed(1)}%
              </span>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[11px]" style={{ color: "#94A3B8" }}>
        Current failure rate: {failureRate.toFixed(1)}%
      </p>
    </div>
  );
}

export default function WorkflowMetricsPage() {
  const { data, isLoading, isError } = useWorkflowMetrics();

  return (
    <div className="mx-auto max-w-7xl space-y-4 pb-4">
      {/* Hero */}
      <div
        className="border-b pb-4"
        style={{ borderColor: "rgba(255,255,255,0.06)" }}
      >
        <p className="route-label mb-1">Workflow Intelligence</p>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h1 className="page-hero-title">Automation Reliability Center</h1>
          {data?.latest_workflow_event_at && (
            <span className="mb-1 text-[12px]" style={{ color: "#94A3B8" }}>
              Last event: {formatDateShort(data.latest_workflow_event_at)}
            </span>
          )}
        </div>
        <p className="text-[13px] leading-relaxed max-w-2xl" style={{ color: "#94A3B8" }}>
          Pipeline automation health: success rates, action distribution, and source breakdown
          across all workflow events processed by the fraud triage system.
        </p>
      </div>

      {isError && (
        <div
          className="rounded-lg px-4 py-2.5 text-[13px]"
          style={{ background: "rgba(255,77,77,0.07)", border: "1px solid rgba(255,77,77,0.22)", color: "#FF4D4D" }}
        >
          Could not load reliability metrics. Check API connectivity.
        </div>
      )}

      {isLoading && (
        <>
          <Skeleton className="h-[72px]" />
          <div className="grid grid-cols-2 gap-3">
            <Skeleton className="h-[84px]" />
            <Skeleton className="h-[84px]" />
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-[68px]" />
            ))}
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Skeleton className="h-52" />
            <Skeleton className="h-52" />
            <Skeleton className="h-52" />
          </div>
        </>
      )}

      {data && (
        <>
          {data.total_workflow_events === 0 && <HostedProfileNote />}
          <ReliabilityStatusStrip metrics={data} />
          <OperationalDiagnosis metrics={data} />
          <ReliabilityTargetPanel metrics={data} />
          <MetricsGrid metrics={data} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <ActionBreakdownChart data={data.events_by_workflow_action} />
            <SourceBreakdownChart data={data.events_by_source} />
            <StatusBreakdownChart data={data.events_by_status} />
          </div>
        </>
      )}
    </div>
  );
}
