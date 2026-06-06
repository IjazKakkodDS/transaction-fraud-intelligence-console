import { type Prediction } from "@/types/case";
import { formatUSD, formatRiskScore, formatDateFull } from "@/lib/utils";

type BadgeType = "danger" | "warn" | "success" | "info" | "neutral";

const BADGE_STYLES: Record<BadgeType, React.CSSProperties> = {
  danger:  { color: "#FF4D4D", background: "rgba(255,77,77,0.10)",   border: "1px solid rgba(255,77,77,0.28)"   },
  warn:    { color: "#F59E0B", background: "rgba(245,158,11,0.10)",  border: "1px solid rgba(245,158,11,0.28)"  },
  success: { color: "#10B981", background: "rgba(16,185,129,0.10)",  border: "1px solid rgba(16,185,129,0.28)"  },
  info:    { color: "#22D3EE", background: "rgba(34,211,238,0.10)",  border: "1px solid rgba(34,211,238,0.28)"  },
  neutral: { color: "#8B949E", background: "rgba(139,148,158,0.10)", border: "1px solid rgba(139,148,158,0.20)" },
};

function Badge({ type, label }: { type: BadgeType; label: string }) {
  return (
    <span
      className="inline-flex items-center rounded-md px-2.5 py-1 text-[12px] font-semibold tracking-wide"
      style={BADGE_STYLES[type]}
    >
      {label}
    </span>
  );
}

function decisionType(d: string | null): BadgeType {
  return d === "BLOCK" ? "danger" : d === "REVIEW" ? "warn" : d === "APPROVE" ? "success" : "neutral";
}

function analystType(s: string | null): BadgeType {
  if (s === "CONFIRMED_FRAUD") return "danger";
  if (s === "FALSE_POSITIVE") return "info";
  if (s === "APPROVED") return "success";
  return "neutral";
}

function topBorderColor(decision: string | null): string {
  if (decision === "BLOCK") return "#FF4D4D";
  if (decision === "REVIEW") return "#F59E0B";
  if (decision === "APPROVE") return "#10B981";
  return "rgba(255,255,255,0.14)";
}

interface CaseHeaderProps {
  caseData: Prediction;
}

export function CaseHeader({ caseData }: CaseHeaderProps) {
  return (
    <div
      className="card px-6 py-5"
      style={{ borderTop: `3px solid ${topBorderColor(caseData.decision)}` }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            className="font-mono text-[28px] font-bold tabular-nums leading-none"
            style={{ color: "#F0F6FC" }}
          >
            #{caseData.id}
          </h2>
          {caseData.transaction_id && (
            <p className="mt-2 font-mono text-[12px]" style={{ color: "#4B5563" }}>
              {caseData.transaction_id}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {caseData.decision && (
            <Badge type={decisionType(caseData.decision)} label={caseData.decision} />
          )}
          <Badge
            type={analystType(caseData.analyst_status)}
            label={
              caseData.analyst_status === "CONFIRMED_FRAUD" ? "CONFIRMED" :
              caseData.analyst_status === "FALSE_POSITIVE"  ? "FALSE POSITIVE" :
              caseData.analyst_status === "APPROVED"        ? "APPROVED" :
              "UNREVIEWED"
            }
          />
        </div>
      </div>
      <div
        className="mt-5 flex flex-wrap gap-6 pt-4"
        style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div>
          <p className="metric-label mb-1">Amount</p>
          <p className="text-[22px] font-bold tabular-nums" style={{ color: "#F0F6FC" }}>
            {formatUSD(caseData.amount)}
          </p>
        </div>
        <div>
          <p className="metric-label mb-1">Final Risk Score</p>
          <p
            className="text-[22px] font-bold tabular-nums"
            style={{
              color:
                caseData.risk_score !== null && caseData.risk_score > 0.7
                  ? "#FF4D4D"
                  : caseData.risk_score !== null && caseData.risk_score > 0.4
                  ? "#F59E0B"
                  : "#F0F6FC",
            }}
          >
            {formatRiskScore(caseData.risk_score)}
          </p>
        </div>
        <div>
          <p className="metric-label mb-1">Transaction Time</p>
          <p className="text-[14px]" style={{ color: "#8B949E" }}>
            {formatDateFull(caseData.timestamp)}
          </p>
        </div>
      </div>
    </div>
  );
}
