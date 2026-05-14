import { type Prediction } from "@/types/case";
import { formatDateFull } from "@/lib/utils";

function Row({
  label,
  children,
  even,
}: {
  label: string;
  children: React.ReactNode;
  even?: boolean;
}) {
  return (
    <div
      className="grid grid-cols-3 gap-3 px-5 py-3"
      style={{
        borderBottom: "1px solid rgba(255,255,255,0.05)",
        background: even ? "rgba(255,255,255,0.02)" : "transparent",
      }}
    >
      <dt className="section-label pt-0.5">{label}</dt>
      <dd className="col-span-2 text-[13px]" style={{ color: "#C9D1D9" }}>
        {children}
      </dd>
    </div>
  );
}

function RuleFlagChip({ value }: { value: number | null }) {
  if (value === null) return <span style={{ color: "#4B5563" }}>—</span>;
  const triggered = Boolean(value);
  return (
    <span
      className="inline-flex items-center rounded-md px-2 py-0.5 text-[12px] font-semibold tracking-wide"
      style={
        triggered
          ? { color: "#F59E0B", background: "rgba(245,158,11,0.10)", border: "1px solid rgba(245,158,11,0.28)" }
          : { color: "#8B949E", background: "rgba(139,148,158,0.08)", border: "1px solid rgba(139,148,158,0.18)" }
      }
    >
      {triggered ? "TRIGGERED" : "NO MATCH"}
    </span>
  );
}

function ReasonsList({ reasons }: { reasons: string | null }) {
  if (!reasons) {
    return <span style={{ color: "#4B5563" }}>No signal factors recorded.</span>;
  }
  const items = reasons.split("|").map((r) => r.trim()).filter(Boolean);
  if (items.length === 0) {
    return <span style={{ color: "#4B5563" }}>No signal factors recorded.</span>;
  }
  const toTitleCase = (s: string) =>
    s.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((reason) => (
        <span
          key={reason}
          className="inline-flex items-center rounded-md px-2 py-0.5 text-[12px] font-medium"
          style={{
            background: "rgba(245,158,11,0.055)",
            border: "1px solid rgba(245,158,11,0.14)",
            color: "#94A3B8",
          }}
        >
          {toTitleCase(reason)}
        </span>
      ))}
    </div>
  );
}

interface CaseMetadataPanelProps {
  caseData: Prediction;
}

export function CaseMetadataPanel({ caseData }: CaseMetadataPanelProps) {
  return (
    <div className="card overflow-hidden">
      <div
        className="px-5 py-4"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <p className="section-label">Risk Evidence</p>
      </div>
      <dl>
        <Row label="Deterministic Rule" even={false}>
          <RuleFlagChip value={caseData.rule_flag} />
        </Row>
        <Row label="Risk Signal Factors" even={true}>
          <ReasonsList reasons={caseData.reasons} />
        </Row>
        <Row label="Analyst Notes" even={false}>
          {caseData.analyst_notes ? (
            <span className="leading-relaxed">{caseData.analyst_notes}</span>
          ) : (
            <span style={{ color: "#4B5563" }}>No analyst notes yet.</span>
          )}
        </Row>
        <Row label="Verdict Recorded" even={true}>
          <span style={{ color: "#8B949E" }}>
            {formatDateFull(caseData.reviewed_at)}
          </span>
        </Row>
      </dl>
    </div>
  );
}
