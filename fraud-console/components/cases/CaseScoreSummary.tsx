import { BrainCircuit, Gavel, ScanSearch, ShieldCheck } from "lucide-react";
import { type Prediction } from "@/types/case";
import { formatRiskScore } from "@/lib/utils";
import { classifyCaseEvidence } from "@/components/cases/caseEvidence";

function signalLabel(value: number | null | undefined, positive: string, negative: string) {
  if (value === null || value === undefined) return "Unavailable";
  return value ? positive : negative;
}

function decisionColor(decision: string | null): string {
  if (decision === "BLOCK") return "#FF4D4D";
  if (decision === "REVIEW") return "#F59E0B";
  if (decision === "APPROVE") return "#10B981";
  return "#8B949E";
}

interface SummaryCellProps {
  label: string;
  value: string;
  detail: string;
  icon: React.ReactNode;
  color?: string;
}

function SummaryCell({ label, value, detail, icon, color = "#CBD5E1" }: SummaryCellProps) {
  return (
    <div className="min-w-0 px-4 py-4">
      <div className="mb-3 flex items-center gap-2" style={{ color: "#6B7280" }}>
        {icon}
        <p className="metric-label">{label}</p>
      </div>
      <p className="text-[20px] font-bold tabular-nums" style={{ color }}>
        {value}
      </p>
      <p className="mt-1 text-[11px] leading-relaxed" style={{ color: "#6B7280" }}>
        {detail}
      </p>
    </div>
  );
}

interface CaseScoreSummaryProps {
  caseData: Prediction;
}

export function CaseScoreSummary({ caseData }: CaseScoreSummaryProps) {
  const evidence = classifyCaseEvidence(caseData.reasons);
  const evidenceCounts = [
    { label: "Base", count: evidence.base.length, color: "#FF8080" },
    {
      label: "Rich / Scenario",
      count: evidence.rich.length + evidence.scenario.length,
      color: "#F59E0B",
    },
    { label: "Behavioural", count: evidence.behavioural.length, color: "#93C5FD" },
    { label: "Graph", count: evidence.graph.length, color: "#A78BFA" },
  ];

  return (
    <section className="card overflow-hidden" aria-labelledby="score-summary-heading">
      <div
        className="flex flex-wrap items-center justify-between gap-2 px-5 py-4"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div>
          <p className="section-label">Decision Evidence</p>
          <h2 id="score-summary-heading" className="mt-1 text-[16px] font-semibold" style={{ color: "#E5E7EB" }}>
            Score and decision summary
          </h2>
        </div>
        <span className="text-[11px]" style={{ color: "#6B7280" }}>
          Persisted scoring output
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2">
        <SummaryCell
          label="Final Risk Score"
          value={formatRiskScore(caseData.risk_score)}
          detail="Final persisted score; no frontend recalculation."
          icon={<ScanSearch size={16} aria-hidden="true" />}
          color={decisionColor(caseData.decision)}
        />
        <SummaryCell
          label="Scoring Decision"
          value={caseData.decision ?? "Unavailable"}
          detail="Decision recorded when the transaction was scored."
          icon={<Gavel size={16} aria-hidden="true" />}
          color={decisionColor(caseData.decision)}
        />
        <SummaryCell
          label="Model Signal"
          value={signalLabel(caseData.model_prediction, "Flagged", "Not flagged")}
          detail="Binary model signal available on the case record."
          icon={<BrainCircuit size={16} aria-hidden="true" />}
        />
        <SummaryCell
          label="Deterministic Rule"
          value={signalLabel(caseData.rule_flag, "Triggered", "No match")}
          detail="Rule result available on the case record."
          icon={<ShieldCheck size={16} aria-hidden="true" />}
        />
      </div>

      <div
        className="grid grid-cols-2 sm:grid-cols-4"
        style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}
      >
        {evidenceCounts.map((item) => (
          <div key={item.label} className="px-4 py-3">
            <p className="font-mono text-[17px] font-semibold tabular-nums" style={{ color: item.color }}>
              {item.count}
            </p>
            <p className="mt-0.5 text-[10px] font-semibold uppercase" style={{ color: "#6B7280" }}>
              {item.label}
            </p>
            <p className="mt-1 text-[10px]" style={{ color: item.count > 0 ? "#8B949E" : "#4B5563" }}>
              {item.count > 0 ? "Evidence present" : "No evidence recorded"}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

