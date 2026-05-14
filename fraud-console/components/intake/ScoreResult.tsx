import Link from "next/link";
import { type Prediction } from "@/types/case";

type ScoreResultProps = {
  prediction: Prediction;
  onReset: () => void;
};

function formatPercent(value: number | null) {
  return value === null ? "N/A" : `${Math.round(value * 100)}%`;
}

function riskColor(score: number | null) {
  if (score !== null && score >= 0.85) return "#FF4D4D";
  if (score !== null && score >= 0.6) return "#F59E0B";
  return "#10B981";
}

function decisionColor(decision: string | null) {
  if (decision === "BLOCK") return "#FF4D4D";
  if (decision === "REVIEW") return "#F59E0B";
  if (decision === "APPROVE") return "#10B981";
  return "#8B949E";
}

function outcomeCopy(decision: string | null) {
  if (decision === "BLOCK") {
    return {
      title: "Critical Review Required",
      text: "High-risk transaction routed for immediate review.",
      color: "#FF4D4D",
    };
  }
  if (decision === "REVIEW") {
    return {
      title: "Analyst Review Required",
      text: "Transaction requires analyst review before final disposition.",
      color: "#F59E0B",
    };
  }
  return {
    title: "Approved Path",
    text: "No major risk signals were returned by the scoring engine.",
    color: "#10B981",
  };
}

const SIGNALS_EVALUATED = [
  "Amount",
  "Time of Day",
  "Payment Method",
  "Region",
  "Merchant Category",
  "International",
  "Device Context",
];

export function ScoreResult({ prediction, onReset }: ScoreResultProps) {
  const reasonList = prediction.reasons?.split("|").filter(Boolean) ?? [];
  const color = riskColor(prediction.risk_score);
  const progress = prediction.risk_score === null ? 0 : Math.round(prediction.risk_score * 100);
  const decision = prediction.decision ?? "UNREVIEWED";
  const outcome = outcomeCopy(prediction.decision);

  const statCards = [
    {
      label: "Decision",
      value: decision,
      color: decisionColor(prediction.decision),
      helper: null as string | null,
    },
    {
      label: "Rule Flag",
      value: prediction.rule_flag === null ? "N/A" : String(prediction.rule_flag),
      color: "#C9D1D9",
      helper: "Fires when a known high-risk pattern is detected.",
    },
    {
      label: "Model Prediction",
      value: prediction.model_prediction === null ? "N/A" : String(prediction.model_prediction),
      color: "#C9D1D9",
      helper:
        "Model output from the enhanced fraud classifier. A value of 1 means the model classified the transaction as high risk.",
    },
  ];

  return (
    <section className="card space-y-5 p-6">
      <div
        className="rounded-md px-4 py-3"
        style={{
          background: `${outcome.color}10`,
          border: `1px solid ${outcome.color}33`,
        }}
      >
        <p className="text-[13px] font-semibold" style={{ color: outcome.color }}>
          {outcome.title}
        </p>
        <p className="mt-1 text-[12px]" style={{ color: "#C9D1D9" }}>
          {outcome.text}
        </p>
      </div>

      {/* Header */}
      <div>
        <p className="section-label">Risk Scoring Complete</p>
        <p className="mt-1 font-mono text-[12px]" style={{ color: "#8B949E" }}>
          {prediction.transaction_id ?? "Transaction reference unavailable"}
        </p>
      </div>

      {/* Risk Score */}
      <div
        className="rounded-md p-4"
        style={{
          background: "rgba(255,255,255,0.025)",
          border: "1px solid rgba(255,255,255,0.07)",
        }}
      >
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="metric-label mb-2">Risk Score</p>
            <p className="text-[44px] font-semibold leading-none tabular-nums" style={{ color }}>
              {formatPercent(prediction.risk_score)}
            </p>
          </div>
          <span
            className="rounded-md px-3 py-1.5 text-[12px] font-semibold"
            style={{
              background: `${decisionColor(prediction.decision)}14`,
              border: `1px solid ${decisionColor(prediction.decision)}33`,
              color: decisionColor(prediction.decision),
            }}
          >
            {decision}
          </span>
        </div>
        <div
          className="mt-3 h-2 overflow-hidden rounded-full"
          style={{ background: "rgba(255,255,255,0.07)" }}
        >
          <div
            className="h-full rounded-full"
            style={{ width: `${progress}%`, background: color }}
          />
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {statCards.map((item) => (
          <div
            key={item.label}
            className="rounded-md px-3 py-3"
            style={{
              background: "rgba(255,255,255,0.035)",
              border: "1px solid rgba(255,255,255,0.07)",
            }}
          >
            <p className="metric-label">{item.label}</p>
            <p className="mt-2 text-[14px] font-semibold" style={{ color: item.color }}>
              {item.value}
            </p>
            {item.helper !== null && (
              <p className="mt-1.5 text-[11px] leading-relaxed" style={{ color: "#6B7280" }}>
                {item.helper}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Signals Evaluated */}
      <div>
        <p className="metric-label mb-2">Signals Evaluated</p>
        <div className="flex flex-wrap gap-1.5">
          {SIGNALS_EVALUATED.map((signal) => (
            <span
              key={signal}
              className="rounded px-2 py-1 text-[11px]"
              style={{
                background: "rgba(255,255,255,0.035)",
                border: "1px solid rgba(255,255,255,0.07)",
                color: "#8B949E",
              }}
            >
              {signal}
            </span>
          ))}
        </div>
      </div>

      {/* Signal Factors */}
      <div>
        <p className="section-label mb-2">Signal Factors</p>
        {reasonList.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {reasonList.map((reason) => (
              <span
                key={reason}
                className="rounded-md px-2 py-1 text-[12px]"
                style={{
                  background: "rgba(34,211,238,0.08)",
                  border: "1px solid rgba(34,211,238,0.18)",
                  color: "#C9D1D9",
                }}
              >
                {reason}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-[13px]" style={{ color: "#8B949E" }}>
            No risk signals were returned for this transaction.
          </p>
        )}
      </div>

      {/* Enhanced Scoring Contract */}
      <div
        className="rounded-md p-4"
        style={{
          background: "rgba(34,211,238,0.03)",
          border: "1px solid rgba(34,211,238,0.10)",
        }}
      >
        <p
          className="text-[11px] font-semibold uppercase tracking-[0.1em]"
          style={{ color: "#22D3EE" }}
        >
          Enhanced Scoring Contract
        </p>
        <p className="mt-2 text-[12px] leading-relaxed" style={{ color: "#8B949E" }}>
          The risk score combines a model prediction and deterministic rule flag. The current scoring engine evaluates amount, transaction timing, payment method, geographic risk, merchant category, international status, and device context.
        </p>
        <p className="mt-2 font-mono text-[11px]" style={{ color: "#6B7280" }}>
          Risk score = 0.6 model output + 0.4 rule flag
        </p>
      </div>

      {/* Operational Handoff */}
      <div
        className="rounded-md p-4"
        style={{
          background: "rgba(255,255,255,0.035)",
          border: "1px solid rgba(255,255,255,0.07)",
        }}
      >
        <p className="section-label">Operational Handoff</p>
        <p className="mt-2 text-[13px] leading-relaxed" style={{ color: "#C9D1D9" }}>
          Open the case dossier to continue AI investigation, analyst verdict capture, workflow dispatch, and audit review.
        </p>
        <p className="mt-2 text-[12px]" style={{ color: "#8B949E" }}>
          Next step: continue the case lifecycle from the dossier.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {["Case Dossier", "AI Investigation", "Analyst Verdict"].map((step, index) => (
            <span
              key={step}
              className="inline-flex items-center gap-2 rounded-md px-2.5 py-1 text-[12px] font-medium"
              style={{
                background: "rgba(34,211,238,0.07)",
                border: "1px solid rgba(34,211,238,0.16)",
                color: "#C9D1D9",
              }}
            >
              <span className="font-mono text-[10px]" style={{ color: "#22D3EE" }}>
                {index + 1}
              </span>
              {step}
            </span>
          ))}
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex flex-wrap items-center gap-3">
        <Link
          href={`/cases/${prediction.id}`}
          className="rounded-md px-4 py-2.5 text-[13px] font-semibold"
          style={{
            background: "rgba(34,211,238,0.10)",
            border: "1px solid rgba(34,211,238,0.28)",
            color: "#22D3EE",
          }}
        >
          Open Case Dossier
        </Link>
        <Link
          href="/queue"
          className="rounded-md px-4 py-2.5 text-[13px] font-semibold"
          style={{
            background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.09)",
            color: "#C9D1D9",
          }}
        >
          View Review Queue
        </Link>
        <button
          type="button"
          onClick={onReset}
          className="rounded-md px-4 py-2.5 text-[13px] font-semibold"
          style={{
            background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.09)",
            color: "#C9D1D9",
          }}
        >
          Submit Another
        </button>
      </div>
    </section>
  );
}
