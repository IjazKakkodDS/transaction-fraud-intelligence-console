"use client";

import { useDailySummary } from "@/lib/hooks/useDailySummary";
import { useStaleCases } from "@/lib/hooks/useStaleCases";
import { useWorkflowEvents } from "@/lib/hooks/useWorkflowEvents";
import { StatsGrid } from "@/components/dashboard/StatsGrid";
import { StaleCasesAlert } from "@/components/dashboard/StaleCasesAlert";
import { DecisionDistributionChart } from "@/components/dashboard/DecisionDistributionChart";
import { WorkflowActivityFeed } from "@/components/dashboard/WorkflowActivityFeed";
import { type DailySummary } from "@/types/workflow";

const COLORS = {
  red: "#FB7185",
  amber: "#FBBF24",
  green: "#34D399",
  cyan: "#22D3EE",
  slate: "#CBD5E1",
  muted: "#94A3B8",
};

function panelStyle(accent = "rgba(148,163,184,0.18)") {
  return {
    background:
      "linear-gradient(180deg, rgba(15,23,42,0.94) 0%, rgba(2,6,23,0.95) 100%)",
    border: `1px solid ${accent}`,
    boxShadow:
      "0 12px 42px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.035)",
  };
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      className="rounded-lg px-4 py-3 text-[13px]"
      style={{
        background: "rgba(251,113,133,0.10)",
        border: "1px solid rgba(251,113,133,0.32)",
        color: COLORS.red,
      }}
    >
      {message}
    </div>
  );
}

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-lg ${className ?? ""}`}
      style={{ background: "rgba(255,255,255,0.04)" }}
    />
  );
}

function RiskSignalBar({
  summary,
  eventCount,
}: {
  summary?: DailySummary;
  eventCount?: number;
}) {
  const riskLevel =
    summary && summary.total_block > 0
      ? "Elevated"
      : summary && summary.unreviewed_cases > 0
      ? "Review"
      : "Stable";
  const riskColor =
    riskLevel === "Elevated" ? COLORS.red : riskLevel === "Review" ? COLORS.amber : COLORS.green;
  const averageRisk = summary ? Math.round(summary.average_risk_score * 100) : 0;
  const signals = [
    { label: "Pipeline Active", value: "Live", color: COLORS.green },
    { label: "Total Cases", value: summary?.total_cases.toLocaleString() ?? "0", color: COLORS.slate },
    { label: "Block Signals", value: summary?.total_block.toLocaleString() ?? "0", color: COLORS.red },
    { label: "Unreviewed", value: summary?.unreviewed_cases.toLocaleString() ?? "0", color: COLORS.amber },
    { label: "Average Risk", value: `${averageRisk}%`, color: COLORS.cyan },
    { label: "Workflow Events", value: eventCount?.toLocaleString() ?? "0", color: COLORS.slate },
  ];

  return (
    <section className="overflow-hidden rounded-lg" style={panelStyle("rgba(34,211,238,0.20)")}>
      <div
        className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
        style={{ borderBottom: "1px solid rgba(148,163,184,0.14)" }}
      >
        <div>
          <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: COLORS.muted }}>
            Risk Signal
          </p>
          <p className="mt-1 text-[12px] font-medium" style={{ color: COLORS.slate }}>
            Live operating state from the fraud triage pipeline.
          </p>
        </div>
        <span
          className="flex items-center gap-2 rounded border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.16em]"
          style={{
            color: riskColor,
            background: `${riskColor}12`,
            borderColor: `${riskColor}55`,
          }}
        >
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60" style={{ background: riskColor }} />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full" style={{ background: riskColor }} />
          </span>
          Risk Level: {riskLevel}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
        {signals.map((signal) => (
          <div
            key={signal.label}
            className="min-w-0 px-4 py-3"
            style={{
              borderRight: "1px solid rgba(148,163,184,0.10)",
              borderBottom: "1px solid rgba(148,163,184,0.08)",
            }}
          >
            <p className="text-[18px] font-semibold tabular-nums" style={{ color: signal.color }}>
              {signal.value}
            </p>
            <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em]" style={{ color: COLORS.muted }}>
              {signal.label}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function VerdictOutcomes({ summary }: { summary: DailySummary }) {
  const reviewPressure =
    summary.total_cases > 0
      ? Math.round(((summary.unreviewed_cases + summary.total_review) / summary.total_cases) * 100)
      : 0;
  const reviewedOutcomes = summary.confirmed_fraud + summary.false_positive;
  const fraudRate =
    reviewedOutcomes > 0
      ? Math.round((summary.confirmed_fraud / reviewedOutcomes) * 100)
      : undefined;

  return (
    <div className="card h-full p-4">
      <div className="mb-3">
        <p className="section-label">Verdict Outcomes</p>
        <p className="mt-1 text-[12px]" style={{ color: COLORS.slate }}>
          Reviewed verdicts and active review load.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {[
          { label: "Confirmed Fraud", value: summary.confirmed_fraud, color: COLORS.red },
          { label: "False Positive", value: summary.false_positive, color: COLORS.green },
          { label: "Review Pressure", value: `${reviewPressure}%`, color: COLORS.amber },
        ].map((item) => (
          <div
            key={item.label}
            className="rounded-md px-3 py-2.5"
            style={{
              background: "rgba(255,255,255,0.025)",
              border: "1px solid rgba(148,163,184,0.12)",
            }}
          >
            <p className="text-[18px] font-semibold tabular-nums" style={{ color: item.color }}>
              {typeof item.value === "number" ? item.value.toLocaleString() : item.value}
            </p>
            <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em]" style={{ color: COLORS.muted }}>
              {item.label}
            </p>
          </div>
        ))}
      </div>

      <div
        className="mt-3 rounded-md px-3 py-2.5"
        style={{
          background: "rgba(255,255,255,0.025)",
          border: "1px solid rgba(148,163,184,0.12)",
        }}
      >
        <div className="flex items-center justify-between gap-3">
          <span className="text-[12px] font-semibold" style={{ color: COLORS.slate }}>
            Fraud Confirmation Rate
          </span>
          {fraudRate !== undefined && (
            <span className="text-[18px] font-semibold tabular-nums" style={{ color: COLORS.red }}>
              {fraudRate}%
            </span>
          )}
        </div>
        {fraudRate === undefined && (
          <p className="mt-1 text-[12px]" style={{ color: COLORS.muted }}>
            Not enough reviewed outcomes yet.
          </p>
        )}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const summary = useDailySummary();
  const stale = useStaleCases(120);
  const events = useWorkflowEvents();

  return (
    <div className="mx-auto w-full max-w-[1400px] space-y-4 overflow-x-hidden">
      <header
        className="rounded-lg px-5 py-3.5"
        style={{
          ...panelStyle("rgba(34,211,238,0.20)"),
          background:
            "linear-gradient(90deg, rgba(15,23,42,0.98), rgba(2,6,23,0.98))",
        }}
      >
        <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: COLORS.muted }}>
          Risk Intelligence
        </p>
        <h1 className="mt-1 font-sans text-[22px] font-semibold leading-tight tracking-tight" style={{ color: "#F8FAFC" }}>
          Risk Command Center
        </h1>
        <p className="mt-1.5 max-w-[820px] text-[13px] leading-relaxed" style={{ color: COLORS.slate }}>
          Live case volume, decision mix, review pressure, and workflow health across the fraud triage pipeline.
        </p>
      </header>

      {summary.isError && (
        <ErrorBanner message="Could not load operational metrics. Check API connectivity." />
      )}

      {summary.isLoading ? (
        <Skeleton className="h-[142px]" />
      ) : (
        <RiskSignalBar summary={summary.data} eventCount={events.data?.length} />
      )}

      {stale.data && <StaleCasesAlert data={stale.data} />}

      <section className="space-y-3">
        <p className="section-label">Case Intelligence</p>
        {summary.isLoading && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-[100px]" />
            ))}
          </div>
        )}
        {summary.data && <StatsGrid summary={summary.data} />}
      </section>

      <section className="space-y-3">
        <p className="section-label">Decision Mix and Review Pressure</p>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
          <div className="min-w-0">
            {summary.isLoading && <Skeleton className="h-[292px]" />}
            {summary.isError && <ErrorBanner message="Decision chart unavailable." />}
            {summary.data && <DecisionDistributionChart summary={summary.data} />}
          </div>
          <div className="min-w-0">
            {summary.isLoading && <Skeleton className="h-[292px]" />}
            {summary.data && <VerdictOutcomes summary={summary.data} />}
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <p className="section-label">Workflow Health</p>
        {events.isLoading && <Skeleton className="h-72" />}
        {events.isError && <ErrorBanner message="Workflow activity unavailable." />}
        {events.data && <WorkflowActivityFeed events={events.data} />}
      </section>
    </div>
  );
}
