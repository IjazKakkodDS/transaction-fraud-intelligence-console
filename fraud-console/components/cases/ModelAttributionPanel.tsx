"use client";

import { BrainCircuit } from "lucide-react";
import { useCaseExplanation } from "@/lib/hooks/useCaseExplanation";
import { type FeatureContribution } from "@/lib/api/explain";

const FEATURE_LABELS: Record<string, string> = {
  amount: "Transaction Amount",
  is_high_amount: "High Value Flag",
  is_night_transaction: "Night Transaction",
  is_international: "International",
  is_high_risk_payment_method: "High-Risk Payment Method",
  is_high_risk_country: "High-Risk Country",
  is_high_risk_merchant_category: "High-Risk Merchant Category",
  has_device_id: "Device Present",
  is_mobile_device: "Mobile Device",
};

function ContributionBar({ entry, maxAbs }: { entry: FeatureContribution; maxAbs: number }) {
  const isPositive = entry.direction === "increases_risk";
  const barColor = isPositive ? "#FF4D4D" : "#10B981";
  const widthPct = maxAbs > 0 ? Math.round((Math.abs(entry.contribution_logit) / maxAbs) * 100) : 0;
  const label = FEATURE_LABELS[entry.feature] ?? entry.feature;
  const sign = isPositive ? "+" : "";
  const valueDisplay =
    entry.feature === "amount"
      ? `$${entry.value.toLocaleString()}`
      : entry.value === 1
      ? "Yes"
      : entry.value === 0
      ? "No"
      : String(entry.value);

  return (
    <div className="flex items-center gap-3 py-1.5">
      <span
        className="w-5 shrink-0 text-center font-mono text-[10px] font-semibold"
        style={{ color: "#4B5563" }}
      >
        {entry.rank}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-[12px] font-medium" style={{ color: "#D1D5DB" }}>
            {label}
          </span>
          <div className="flex shrink-0 items-center gap-2">
            <span className="font-mono text-[10px]" style={{ color: "#6B7280" }}>
              {valueDisplay}
            </span>
            <span
              className="w-[52px] text-right font-mono text-[11px] font-semibold tabular-nums"
              style={{ color: barColor }}
            >
              {sign}{entry.contribution_logit.toFixed(3)}
            </span>
          </div>
        </div>
        <div
          className="mt-1 h-1 overflow-hidden rounded-full"
          style={{ background: "rgba(255,255,255,0.06)" }}
        >
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{ width: `${widthPct}%`, background: barColor, opacity: 0.75 }}
          />
        </div>
      </div>
    </div>
  );
}

interface ModelAttributionPanelProps {
  caseId: number;
}

export function ModelAttributionPanel({ caseId }: ModelAttributionPanelProps) {
  const { data, isLoading, isError } = useCaseExplanation(caseId);

  if (isLoading) {
    return (
      <section
        className="card"
        aria-label="Model Attribution loading"
      >
        <div
          className="px-5 py-4"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
        >
          <p className="section-label">Model Attribution</p>
        </div>
        <div className="space-y-3 px-5 py-4">
          {[80, 65, 55, 45].map((w) => (
            <div key={w} className="flex items-center gap-3">
              <div className="h-3 w-4 animate-pulse rounded" style={{ background: "rgba(255,255,255,0.06)" }} />
              <div className="flex-1 space-y-1.5">
                <div className="h-3 animate-pulse rounded" style={{ width: `${w}%`, background: "rgba(255,255,255,0.06)" }} />
                <div className="h-1 animate-pulse rounded-full" style={{ width: `${w - 10}%`, background: "rgba(255,255,255,0.04)" }} />
              </div>
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (isError || !data) {
    return (
      <section className="card" aria-label="Model Attribution unavailable">
        <div
          className="flex items-center gap-2 px-5 py-4"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
        >
          <BrainCircuit size={14} style={{ color: "#4B5563" }} />
          <p className="section-label">Model Attribution</p>
        </div>
        <p className="px-5 py-4 text-[12px]" style={{ color: "#4B5563" }}>
          Attribution unavailable for this case.
        </p>
      </section>
    );
  }

  const allEntries = [...data.features].sort(
    (a, b) => Math.abs(b.contribution_logit) - Math.abs(a.contribution_logit),
  );
  const maxAbs = allEntries.length > 0 ? Math.abs(allEntries[0].contribution_logit) : 1;

  return (
    <section className="card overflow-hidden" aria-labelledby="model-attribution-heading">
      <div
        className="flex flex-wrap items-center justify-between gap-2 px-5 py-4"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div className="flex items-center gap-2">
          <BrainCircuit size={14} style={{ color: "#93C5FD" }} aria-hidden="true" />
          <div>
            <p className="section-label">Model Attribution</p>
            <h2 id="model-attribution-heading" className="mt-0.5 text-[14px] font-semibold" style={{ color: "#E5E7EB" }}>
              Baseline model feature contributions
            </h2>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span
            className="rounded border px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-wider"
            style={{ color: "#93C5FD", borderColor: "rgba(147,197,253,0.25)", background: "rgba(147,197,253,0.06)" }}
          >
            {data.explanation_method}
          </span>
          <span className="text-[11px]" style={{ color: "#4B5563" }}>
            bias {data.bias_logit.toFixed(3)}
          </span>
        </div>
      </div>

      <div className="px-5 py-4">
        <div className="mb-3 flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: "#FF4D4D", opacity: 0.75 }} />
            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "#6B7280" }}>
              Increases risk
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: "#10B981", opacity: 0.75 }} />
            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "#6B7280" }}>
              Decreases risk
            </span>
          </div>
          <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "#4B5563" }}>
            Logit units
          </span>
        </div>

        <div className="divide-y" style={{ borderColor: "rgba(255,255,255,0.04)" }}>
          {allEntries.map((entry) => (
            <ContributionBar key={entry.feature} entry={entry} maxAbs={maxAbs} />
          ))}
        </div>
      </div>

      {data.notes.length > 0 && (
        <div
          className="px-5 pb-4"
          style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}
        >
          <ul className="mt-3 space-y-1">
            {data.notes.map((note, i) => (
              <li key={i} className="flex gap-1.5 text-[10.5px] leading-snug" style={{ color: "#4B5563" }}>
                <span className="mt-0.5 shrink-0">·</span>
                <span>{note}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
