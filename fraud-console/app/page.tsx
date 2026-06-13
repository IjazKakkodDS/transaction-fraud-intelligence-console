"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  ArrowRight,
  BarChart2,
  ClipboardList,
  ExternalLink,
  LayoutDashboard,
} from "lucide-react";
import { useDailySummary } from "@/lib/hooks/useDailySummary";
import { useStaleCases } from "@/lib/hooks/useStaleCases";
import { type DailySummary } from "@/types/workflow";
import { seedDemoState } from "@/lib/api/demo";

const COLORS = {
  red: "#FB7185",
  amber: "#FBBF24",
  green: "#34D399",
  cyan: "#22D3EE",
  slate: "#CBD5E1",
  muted: "#94A3B8",
  quiet: "#64748B",
};

const PIPELINE = [
  {
    step: "01",
    label: "INGEST",
    desc: "Transaction received",
    color: COLORS.cyan,
    active: false,
    orderClass: "lg:order-1",
  },
  {
    step: "02",
    label: "SCORE",
    desc: "Risk computed",
    color: COLORS.cyan,
    active: true,
    orderClass: "lg:order-2",
  },
  {
    step: "03",
    label: "TRIAGE",
    desc: "Priority assigned",
    color: COLORS.amber,
    active: true,
    orderClass: "lg:order-3",
  },
  {
    step: "04",
    label: "INVESTIGATE",
    desc: "AI brief ready",
    color: COLORS.amber,
    active: true,
    orderClass: "lg:order-4",
  },
  {
    step: "05",
    label: "VERDICT",
    desc: "Human decision",
    color: COLORS.green,
    active: true,
    orderClass: "lg:order-5",
  },
  {
    step: "06",
    label: "AUDIT",
    desc: "Evidence preserved",
    color: COLORS.green,
    active: false,
    orderClass: "lg:order-6",
  },
];

const PRIORITIES = [
  {
    tag: "CRITICAL",
    title: "Clear BLOCK cases first",
    detail: "High-risk decisions should exit the queue before routine review.",
    color: COLORS.red,
  },
  {
    tag: "PENDING",
    title: "Review unreviewed decisions",
    detail: "Keep analyst attention on decisions without human confirmation.",
    color: COLORS.amber,
  },
  {
    tag: "INVESTIGATE",
    title: "Generate investigation briefs",
    detail: "Produce evidence packets for faster escalation review.",
    color: COLORS.cyan,
  },
  {
    tag: "MONITOR",
    title: "Check workflow dispatch health",
    detail: "Protect the event pipeline that creates downstream audit evidence.",
    color: COLORS.amber,
  },
  {
    tag: "VERIFY",
    title: "Confirm audit trail coverage",
    detail: "Validate that case decisions remain traceable end to end.",
    color: COLORS.green,
  },
];

const GOVERNANCE = [
  {
    label: "VERDICT GOVERNANCE",
    title: "Human-in-the-loop verdict control",
    desc: "Escalated cases require explicit analyst confirmation before final disposition.",
    color: COLORS.green,
  },
  {
    label: "DECISION LINEAGE",
    title: "Traceable analyst decisions",
    desc: "Every verdict remains linked to case context, notes, status, and workflow state.",
    color: COLORS.cyan,
  },
  {
    label: "INVESTIGATION INTELLIGENCE",
    title: "Evidence-led investigation briefs",
    desc: "AI-generated briefs accelerate review without replacing analyst judgment.",
    color: COLORS.amber,
  },
  {
    label: "AUDIT CONTINUITY",
    title: "Workflow events as audit evidence",
    desc: "Dispatch activity is preserved as durable operational evidence across the case lifecycle.",
    color: COLORS.green,
  },
  {
    label: "LIVE SYSTEM TELEMETRY",
    title: "API-backed operating state",
    desc: "The console reflects current case volume, risk level, and workflow health.",
    color: COLORS.cyan,
  },
];

const NAV_MODULES = [
  {
    href: "/dashboard",
    label: "Live Operations",
    desc: "Case volume, decision mix, stale-case pressure, and workflow throughput.",
    cta: "Open Dashboard",
    accent: COLORS.cyan,
    code: "OPERATIONS",
    Icon: LayoutDashboard,
  },
  {
    href: "/queue",
    label: "Analyst Workbench",
    desc: "Prioritized review, evidence inspection, investigation briefs, and final verdict capture.",
    cta: "Open Queue",
    accent: COLORS.amber,
    code: "ANALYST REVIEW",
    Icon: ClipboardList,
  },
  {
    href: "/workflow/metrics",
    label: "Reliability Center",
    desc: "Dispatch health, failure monitoring, source activity, and audit coverage.",
    cta: "Open Reliability",
    accent: COLORS.green,
    code: "RELIABILITY",
    Icon: BarChart2,
  },
  {
    href: "/workflow/events",
    label: "Audit Trail",
    desc: "Workflow events, dispatch outcomes, and audit evidence across the case lifecycle.",
    cta: "Open Audit Trail",
    accent: COLORS.green,
    code: "WORKFLOW EVENTS",
    Icon: Activity,
  },
];

function panelStyle(accent = "rgba(148,163,184,0.18)") {
  return {
    background:
      "linear-gradient(180deg, rgba(15,23,42,0.94) 0%, rgba(2,6,23,0.95) 100%)",
    border: `1px solid ${accent}`,
    boxShadow:
      "0 12px 42px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.035)",
  };
}

function CommandStyles() {
  return (
    <style>{`
      @keyframes rail-signal-x {
        0% { transform: translateX(-120%); opacity: 0; }
        18% { opacity: .82; }
        72% { opacity: .82; }
        100% { transform: translateX(260%); opacity: 0; }
      }

      @keyframes rail-signal-y {
        0% { transform: translateY(-120%); opacity: 0; }
        18% { opacity: .74; }
        72% { opacity: .74; }
        100% { transform: translateY(220%); opacity: 0; }
      }

      @keyframes node-pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(34, 211, 238, .0); }
        50% { box-shadow: 0 0 0 4px rgba(34, 211, 238, .08); }
      }

      .pipeline-signal-x {
        animation: rail-signal-x 6.8s ease-in-out infinite;
      }

      .pipeline-signal-y {
        animation: rail-signal-y 6.8s ease-in-out infinite;
      }

      .command-node-active {
        animation: node-pulse 2.6s ease-in-out infinite;
      }
    `}</style>
  );
}

function StatusChip({
  label,
  color,
}: {
  label: string;
  color: string;
}) {
  return (
    <span
      className="flex items-center gap-2 rounded border px-3 py-1.5 font-sans text-[10px] font-semibold uppercase tracking-[0.16em]"
      style={{
        color,
        borderColor: `${color}55`,
        background: `${color}12`,
      }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}

function MissionKpis({
  summary,
  staleCount,
}: {
  summary: DailySummary;
  staleCount?: number;
}) {
  const metrics = [
    { label: "Total Cases", value: summary.total_cases, color: COLORS.slate },
    { label: "Block Signals", value: summary.total_block, color: COLORS.red },
    { label: "Under Review", value: summary.total_review, color: COLORS.amber },
    { label: "Approved", value: summary.total_approve, color: COLORS.green },
    { label: "Unreviewed", value: summary.unreviewed_cases, color: COLORS.amber },
    { label: "Confirmed Fraud", value: summary.confirmed_fraud, color: COLORS.red },
  ];
  const riskLevel =
    summary.total_block > 0
      ? "ELEVATED"
      : summary.unreviewed_cases > 0 || (staleCount ?? 0) > 0
      ? "REVIEW"
      : "STABLE";
  const riskLevelColor =
    riskLevel === "ELEVATED" ? COLORS.red : riskLevel === "REVIEW" ? COLORS.amber : COLORS.green;

  return (
    <section className="overflow-hidden rounded-lg" style={panelStyle("rgba(148,163,184,0.18)")}>
      <div
        className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
        style={{ borderBottom: "1px solid rgba(148,163,184,0.14)" }}
      >
        <div>
          <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: COLORS.muted }}>
            Live Risk Snapshot
          </p>
          <p className="mt-1 text-[12px] font-medium" style={{ color: COLORS.muted }}>
            Current case volume, decision mix, and analyst review status.
          </p>
        </div>
        <StatusChip label={`Risk Level: ${riskLevel}`} color={riskLevelColor} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="min-w-0 px-4 py-4"
            style={{
              borderRight: "1px solid rgba(148,163,184,0.10)",
              borderBottom: "1px solid rgba(148,163,184,0.08)",
            }}
          >
            <p
              className="font-sans text-[26px] font-semibold leading-none tabular-nums"
              style={{ color: metric.value > 0 || metric.label === "Total Cases" ? metric.color : COLORS.muted }}
            >
              {metric.value.toLocaleString()}
            </p>
            <p className="mt-2 text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: COLORS.slate }}>
              {metric.label}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function FraudPipelineMap() {
  return (
    <section className="relative overflow-hidden rounded-lg" style={panelStyle("rgba(34,211,238,0.22)")}>
      <div
        className="flex flex-wrap items-center justify-between gap-3 px-5 py-3"
        style={{ borderBottom: "1px solid rgba(148,163,184,0.14)" }}
      >
        <div>
          <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: COLORS.muted }}>
            Fraud Operating Flow
          </p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight" style={{ color: "#F8FAFC" }}>
            Fraud Decision Pipeline
          </h2>
        </div>
        <div className="flex items-center gap-2 font-sans text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: COLORS.green }}>
          <span className="h-2 w-2 rounded-full command-node-active" style={{ background: COLORS.green }} />
          Active telemetry
        </div>
      </div>

      <div className="relative px-4 py-3">
        <div
          className="absolute left-7 right-7 top-[68px] hidden h-px lg:block"
          style={{ background: "linear-gradient(90deg, transparent, rgba(34,211,238,0.32), rgba(251,191,36,0.32), rgba(52,211,153,0.32), transparent)" }}
        />
        <div
          className="absolute bottom-[68px] left-7 right-7 hidden h-px lg:block"
          style={{ background: "linear-gradient(90deg, transparent, rgba(251,191,36,0.32), rgba(52,211,153,0.32), transparent)" }}
        />
        <div
          className="absolute right-[16.7%] top-[68px] hidden h-[calc(100%-136px)] w-px lg:block"
          style={{ background: "linear-gradient(180deg, rgba(251,191,36,0.42), rgba(52,211,153,0.28))" }}
        />

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {PIPELINE.map((stage, idx) => (
            <div key={stage.label} className={`relative min-w-0 ${stage.orderClass}`}>
              {(idx === 0 || idx === 1 || idx === 3 || idx === 4) && (
                <div
                  className="absolute right-[-12px] top-[39px] z-20 hidden h-2 w-6 overflow-hidden lg:block"
                  style={{
                    background: `linear-gradient(90deg, ${stage.color}30, ${stage.color}75, ${stage.color}30)`,
                    borderTop: `1px solid ${stage.color}70`,
                  }}
                >
                  <span
                    className="pipeline-signal-x absolute left-0 top-[1px] h-[5px] w-4 rounded-full"
                    style={{
                      animationDelay:
                        idx === 0 ? "0s" : idx === 1 ? "1.2s" : idx === 3 ? "3.6s" : "4.8s",
                      background:
                        idx === 3 || idx === 4
                          ? "rgba(52,211,153,0.82)"
                          : "rgba(34,211,238,0.86)",
                      boxShadow:
                        idx === 3 || idx === 4
                          ? "0 0 10px rgba(52,211,153,0.34)"
                          : "0 0 10px rgba(34,211,238,0.36)",
                    }}
                  />
                  <span
                    className="absolute right-[1px] top-[1px] h-0 w-0 border-y-[3px] border-l-[5px] border-y-transparent"
                    style={{ borderLeftColor: stage.color }}
                  />
                </div>
              )}
              {idx === 2 && (
                <div
                  className="absolute bottom-[-14px] left-1/2 z-20 hidden h-8 w-3 -translate-x-1/2 overflow-hidden lg:block"
                  style={{
                    background: `linear-gradient(180deg, ${stage.color}26, ${COLORS.green}78, ${COLORS.green}26)`,
                    borderLeft: `1px solid ${stage.color}70`,
                  }}
                >
                  <span
                    className="pipeline-signal-y absolute left-[3px] top-0 h-4 w-[5px] rounded-full"
                    style={{
                      animationDelay: "2.4s",
                      background: "rgba(52,211,153,0.82)",
                      boxShadow: "0 0 10px rgba(52,211,153,0.32)",
                    }}
                  />
                  <span
                    className="absolute bottom-[1px] left-[2px] h-0 w-0 border-x-[4px] border-t-[6px] border-x-transparent"
                    style={{ borderTopColor: COLORS.green }}
                  />
                </div>
              )}
              <div
                className="relative flex min-h-[104px] flex-col justify-between rounded-md p-3.5"
                style={{
                  background:
                    "linear-gradient(180deg, rgba(15,23,42,0.78), rgba(15,23,42,0.58))",
                  border: `1px solid ${stage.color}38`,
                }}
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <span className="font-sans text-[11px] font-semibold tracking-tight" style={{ color: COLORS.muted }}>
                      {stage.step}
                    </span>
                    <span
                      className={stage.active ? "h-2 w-2 rounded-full command-node-active" : "h-2 w-2 rounded-full"}
                      style={{
                        background: stage.color,
                        opacity: stage.active ? 1 : 0.54,
                      }}
                    />
                  </div>
                  <p className="mt-2.5 text-[12px] font-semibold uppercase tracking-[0.12em]" style={{ color: stage.color }}>
                    {stage.label}
                  </p>
                  <p className="mt-1 text-[12px] font-medium leading-snug" style={{ color: COLORS.slate }}>
                    {stage.desc}
                  </p>
                </div>
                <div className="mt-2.5 flex items-center gap-2">
                  <div className="h-px flex-1" style={{ background: `${stage.color}55` }} />
                  <span className="font-sans text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: COLORS.muted }}>
                    {stage.active ? "live" : "ready"}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function OperationalPriorities({ staleCount }: { staleCount?: number }) {
  return (
    <aside className="overflow-hidden rounded-lg" style={panelStyle("rgba(251,191,36,0.22)")}>
      <div className="px-4 py-2.5" style={{ borderBottom: "1px solid rgba(148,163,184,0.14)" }}>
        <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: COLORS.muted }}>
          Action Queue
        </p>
        <h2 className="mt-1 font-sans text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: COLORS.muted }}>
          Operational Priorities
        </h2>
      </div>

      {(staleCount ?? 0) > 0 && (
        <div className="px-4 py-2.5" style={{ borderBottom: "1px solid rgba(148,163,184,0.12)" }}>
          <div className="flex items-center justify-between gap-3">
            <span className="font-sans text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: COLORS.amber }}>
              SLA Pressure
            </span>
            <span className="font-sans text-[16px] font-semibold tabular-nums" style={{ color: COLORS.amber }}>
              {staleCount}
            </span>
          </div>
          <p className="mt-1 text-[12px]" style={{ color: COLORS.slate }}>
            Stale case{staleCount === 1 ? "" : "s"} require analyst attention.
          </p>
        </div>
      )}

      <div>
        {PRIORITIES.map((item) => (
          <div
            key={item.tag}
            className="grid grid-cols-[94px_minmax(0,1fr)] gap-3 px-4 py-2.5"
            style={{ borderBottom: "1px solid rgba(148,163,184,0.10)" }}
          >
            <span
              className="h-fit rounded border px-2 py-0.5 text-center font-sans text-[9px] font-semibold uppercase tracking-[0.12em]"
              style={{
                color: item.color,
                background: `${item.color}10`,
                borderColor: `${item.color}55`,
              }}
            >
              {item.tag}
            </span>
            <div className="min-w-0">
              <p className="text-[13px] font-semibold leading-snug" style={{ color: COLORS.slate }}>
                {item.title}
              </p>
              <p className="mt-0.5 text-[11px] leading-snug" style={{ color: COLORS.muted }}>
                {item.detail}
              </p>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}

function GovernanceControls() {
  return (
    <section className="overflow-hidden rounded-lg" style={panelStyle("rgba(52,211,153,0.20)")}>
      <div className="px-4 py-2.5" style={{ borderBottom: "1px solid rgba(148,163,184,0.14)" }}>
        <p className="font-sans text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: COLORS.muted }}>
          Control / Governance
        </p>
        <h2 className="mt-1 font-sans text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: COLORS.muted }}>
          Governance & Control Layer
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5">
        {GOVERNANCE.map((item) => (
          <div
            key={item.label}
            className="min-w-0 px-3.5 py-3"
            style={{ borderRight: "1px solid rgba(148,163,184,0.10)" }}
          >
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: item.color, opacity: 0.82 }} />
              <span className="min-w-0 text-[8.5px] font-semibold uppercase leading-snug tracking-[0.1em]" style={{ color: COLORS.muted }}>
                {item.label}
              </span>
            </div>
            <p className="mt-2 text-[12px] font-medium leading-snug" style={{ color: COLORS.slate }}>
              {item.title}
            </p>
            <p className="mt-1.5 text-[10.5px] leading-snug" style={{ color: COLORS.muted }}>
              {item.desc}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function ProductModules() {
  return (
    <section>
      <div className="mb-2 flex items-center justify-between">
        <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: COLORS.muted }}>
          Operational Modules
        </p>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        {NAV_MODULES.map((mod) => {
          const { Icon } = mod;
          return (
            <Link
              key={mod.href}
              href={mod.href}
              className="group flex min-h-[148px] flex-col rounded-lg p-4 transition duration-200 hover:-translate-y-0.5"
              style={panelStyle(`${mod.accent}33`)}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div
                    className="flex h-8 w-8 items-center justify-center rounded-md border"
                    style={{ background: `${mod.accent}10`, borderColor: `${mod.accent}55` }}
                  >
                    <Icon className="h-3.5 w-3.5" style={{ color: mod.accent }} />
                  </div>
                  <span className="font-sans text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: mod.accent }}>
                    {mod.code}
                  </span>
                </div>
                <span className="font-sans text-[9px] uppercase tracking-[0.14em]" style={{ color: COLORS.muted }}>
                  {mod.href}
                </span>
              </div>
              <div className="mt-4 min-w-0">
                <p className="text-[14px] font-semibold" style={{ color: COLORS.slate }}>
                  {mod.label}
                </p>
                <p className="mt-1.5 text-[11px] leading-snug" style={{ color: COLORS.muted }}>
                  {mod.desc}
                </p>
              </div>
              <div className="mt-auto flex items-center gap-2 pt-4">
                <span className="text-[12px] font-semibold" style={{ color: mod.accent }}>
                  {mod.cta}
                </span>
                <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" style={{ color: mod.accent }} />
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

const INVESTIGATION_CAPABILITIES = [
  {
    label: "4-Layer Fraud Scoring",
    detail: "Hybrid ML/rule base, enriched signals, behavioural profiling, and graph mule-network detection",
    color: COLORS.cyan,
  },
  {
    label: "Evidence-Led Case Dossier",
    detail: "Grouped evidence by intelligence layer — behavioural anomalies, graph indicators, reason codes, lifecycle timeline",
    color: COLORS.amber,
  },
  {
    label: "Model Attribution",
    detail: "XGBoost feature contributions via TreeSHAP — per-feature logit impact ranked by magnitude",
    color: COLORS.cyan,
  },
  {
    label: "AI Investigation Brief",
    detail: "AGENT_VERSION-tagged brief with recommendation, confidence, escalation logic, and playbook retrieval evidence",
    color: COLORS.amber,
  },
  {
    label: "Analyst Decision Loop",
    detail: "Verdict capture, false-positive classification, workflow dispatch, and case-scoped automation audit",
    color: COLORS.green,
  },
  {
    label: "Reliability and Scale",
    detail: "SLO-style pipeline health metrics and 10M-transaction portfolio risk scan benchmark evidence",
    color: COLORS.green,
  },
];

const INVESTIGATION_FLOW = [
  "Overview", "Intake", "Queue", "Case Dossier",
  "Attribution", "AI Brief", "Workflow Audit", "Reliability", "Risk Scan",
];

function GuidedInvestigationPanel() {
  const router = useRouter();
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  async function handleLaunch() {
    setStatus("loading");
    setErrorMsg("");
    try {
      const result = await seedDemoState();
      router.push(result.case_url ?? "/queue");
    } catch (err) {
      setStatus("error");
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Demo seed failed. Check API connectivity.",
      );
    }
  }

  return (
    <section className="overflow-hidden rounded-lg" style={panelStyle("rgba(34,211,238,0.15)")}>
      <div className="px-5 pb-4 pt-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p
                className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em]"
                style={{ color: COLORS.muted }}
              >
                Guided Investigation
              </p>
              <span
                className="rounded px-1.5 py-0.5 font-sans text-[9px] font-semibold uppercase tracking-[0.14em]"
                style={{
                  background: "rgba(34,211,238,0.08)",
                  color: COLORS.cyan,
                  border: "1px solid rgba(34,211,238,0.22)",
                }}
              >
                Controlled Workflow Demo
              </span>
            </div>
            <h2 className="mt-1 text-[15px] font-semibold" style={{ color: COLORS.slate }}>
              Guided Investigation Command Panel
            </h2>
            <p className="mt-0.5 text-[12px]" style={{ color: COLORS.muted }}>
              Seeds canonical demo cases and opens the fraud evidence dossier. Walk each system capability end-to-end.
            </p>
          </div>

          <div className="flex shrink-0 flex-col items-end gap-2">
            <button
              onClick={handleLaunch}
              disabled={status === "loading"}
              className="flex items-center gap-2 rounded border px-4 py-2 font-sans text-[12px] font-semibold uppercase tracking-[0.12em] transition hover:opacity-80 disabled:cursor-wait disabled:opacity-50"
              style={{
                color: COLORS.cyan,
                borderColor: `${COLORS.cyan}55`,
                background: `${COLORS.cyan}10`,
              }}
            >
              {status === "loading" ? (
                <>
                  <span className="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent" />
                  Seeding...
                </>
              ) : (
                <>
                  Launch Guided Investigation
                  <ArrowRight className="h-3.5 w-3.5" />
                </>
              )}
            </button>

            {status === "error" && (
              <p
                className="max-w-[300px] text-right text-[11px] leading-snug"
                style={{ color: COLORS.red }}
              >
                {errorMsg}
                <span className="mt-0.5 block" style={{ color: COLORS.muted }}>
                  Fallback:{" "}
                  <span style={{ fontFamily: "monospace" }}>
                    python scripts/demo_seed.py
                  </span>
                </span>
              </p>
            )}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {INVESTIGATION_CAPABILITIES.map((cap) => (
            <div
              key={cap.label}
              className="rounded-md px-3 py-2.5"
              style={{
                background: "rgba(255,255,255,0.02)",
                border: "1px solid rgba(255,255,255,0.06)",
              }}
            >
              <div className="flex items-center gap-1.5">
                <span
                  className="h-1.5 w-1.5 flex-shrink-0 rounded-full"
                  style={{ background: cap.color }}
                />
                <p className="text-[12px] font-semibold" style={{ color: COLORS.slate }}>
                  {cap.label}
                </p>
              </div>
              <p className="mt-1 text-[11px] leading-snug" style={{ color: COLORS.muted }}>
                {cap.detail}
              </p>
            </div>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-x-1 gap-y-1">
          <span
            className="font-sans text-[10px] font-semibold uppercase tracking-[0.1em]"
            style={{ color: COLORS.quiet }}
          >
            Workflow Path:
          </span>
          {INVESTIGATION_FLOW.map((step, i) => (
            <span key={step} className="flex items-center gap-1">
              <span
                className="font-sans text-[10px] font-semibold uppercase tracking-[0.1em]"
                style={{ color: COLORS.quiet }}
              >
                {step}
              </span>
              {i < INVESTIGATION_FLOW.length - 1 && (
                <span style={{ color: COLORS.quiet, fontSize: "10px" }}>›</span>
              )}
            </span>
          ))}
        </div>

        <div
          className="mt-3 flex flex-wrap items-center gap-4 pt-3"
          style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}
        >
          <Link
            href="/queue"
            className="flex items-center gap-1 font-sans text-[11px] font-semibold uppercase tracking-[0.1em] transition hover:opacity-70"
            style={{ color: COLORS.muted }}
          >
            Open Review Queue
            <ArrowRight className="h-3 w-3" />
          </Link>
          <Link
            href="/risk-scan?scan_id=aa0971d2-bdb6-49c7-bac3-fa355aa161ad"
            className="flex items-center gap-1 font-sans text-[11px] font-semibold uppercase tracking-[0.1em] transition hover:opacity-70"
            style={{ color: COLORS.muted }}
          >
            10M Portfolio Scan
            <ArrowRight className="h-3 w-3" />
          </Link>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 font-sans text-[11px] font-semibold uppercase tracking-[0.1em] transition hover:opacity-70"
            style={{ color: COLORS.muted }}
          >
            View API Docs
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>
    </section>
  );
}

export default function OverviewPage() {
  const summary = useDailySummary();
  const stale = useStaleCases(120);

  return (
    <div className="mx-auto w-full max-w-[1480px] space-y-4 overflow-x-hidden">
      <CommandStyles />

      <header
        className="rounded-lg px-5 py-3.5"
        style={{
          ...panelStyle("rgba(34,211,238,0.20)"),
          background:
            "linear-gradient(90deg, rgba(15,23,42,0.98), rgba(2,6,23,0.98))",
        }}
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: COLORS.muted }}>
              Fraud Risk Intelligence
            </p>
            <h1 className="mt-1 font-sans text-[22px] font-semibold leading-tight tracking-tight" style={{ color: "#F8FAFC" }}>
              Fraud Intelligence Command Center
            </h1>
            <p className="mt-1.5 max-w-[760px] text-[13px] leading-relaxed" style={{ color: COLORS.slate }}>
              Real-time fraud scoring, analyst triage, investigation intelligence, and audit-ready workflow control.
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <StatusChip label="Live System" color={COLORS.green} />
            <StatusChip label="API Connected" color={COLORS.cyan} />
            <StatusChip label="Audit Ready" color={COLORS.green} />
          </div>
        </div>
      </header>

      <GuidedInvestigationPanel />

      {summary.isLoading && (
        <div className="h-[142px] animate-pulse rounded-lg" style={panelStyle("rgba(148,163,184,0.14)")} />
      )}

      {summary.isError && (
        <div
          className="rounded-lg px-4 py-3 text-[13px] font-semibold"
          style={{
            background: "rgba(251,113,133,0.10)",
            border: "1px solid rgba(251,113,133,0.32)",
            color: COLORS.red,
          }}
        >
          Could not load operational metrics. Check API connectivity.
        </div>
      )}

      {summary.data && <MissionKpis summary={summary.data} staleCount={stale.data?.count} />}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <FraudPipelineMap />
        <OperationalPriorities staleCount={stale.data?.count} />
      </div>

      <GovernanceControls />
      <ProductModules />
    </div>
  );
}
