import { type ReviewQueue } from "@/types/case";
import { CaseRowActions } from "@/components/queue/CaseRowActions";
import { formatUSD, formatRiskScore, formatDateShort } from "@/lib/utils";

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
      className="inline-flex items-center rounded-md px-2 py-0.5 text-[12px] font-semibold tracking-wide"
      style={BADGE_STYLES[type]}
    >
      {label}
    </span>
  );
}

function decisionBadge(decision: string | null) {
  if (!decision) return <span style={{ color: "#94A3B8" }}>N/A</span>;
  const map: Record<string, BadgeType> = { BLOCK: "danger", REVIEW: "warn", APPROVE: "success" };
  return <Badge type={map[decision] ?? "neutral"} label={decision} />;
}

function analystBadge(status: string | null) {
  const labelMap: Record<string, string> = {
    CONFIRMED_FRAUD: "CONFIRMED",
    FALSE_POSITIVE:  "FALSE POSITIVE",
    APPROVED:        "APPROVED",
    UNREVIEWED:      "UNREVIEWED",
  };
  const key   = status ?? "UNREVIEWED";
  const label = labelMap[key] ?? key.replace(/_/g, " ");
  const map: Record<string, BadgeType> = {
    CONFIRMED_FRAUD: "danger",
    FALSE_POSITIVE:  "info",
    APPROVED:        "success",
    UNREVIEWED:      "neutral",
  };
  return <Badge type={map[key] ?? "neutral"} label={label} />;
}

type PrioritySpec = { label: string; color: string; bg: string; border: string };

function getPriority(score: number | null, decision: string | null): PrioritySpec {
  if (decision === "BLOCK" || (score !== null && score >= 0.85)) {
    return { label: "P0 Critical", color: "#FB7185", bg: "rgba(251,113,133,0.055)", border: "rgba(251,113,133,0.18)" };
  }
  if (score !== null && score >= 0.65) {
    return { label: "P1 High",     color: "#F59E0B", bg: "rgba(245,158,11,0.06)",   border: "rgba(245,158,11,0.18)"   };
  }
  if (decision === "REVIEW" || (score !== null && score >= 0.3)) {
    return { label: "P2 Review",   color: "#22D3EE", bg: "rgba(34,211,238,0.055)",  border: "rgba(34,211,238,0.16)"   };
  }
  return   { label: "P3 Low",      color: "#10B981", bg: "rgba(16,185,129,0.055)",  border: "rgba(16,185,129,0.14)"   };
}

function ReasonTags({ reasons }: { reasons?: string | null }) {
  const tags = reasons?.split("|").map((t) => t.trim()).filter(Boolean).slice(0, 2) ?? [];
  if (tags.length === 0) return null;
  const formatReason = (tag: string) =>
    tag
      .replace(/_/g, " ")
      .toLowerCase()
      .replace(/^\w/, (c) => c.toUpperCase());

  return (
    <div className="mt-1 flex flex-wrap gap-1">
      {tags.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center rounded px-1.5 py-[1px] text-[9px] font-medium"
          style={{
            background: "rgba(148,163,184,0.045)",
            color: "#94A3B8",
            border: "1px solid rgba(148,163,184,0.10)",
          }}
        >
          {formatReason(tag)}
        </span>
      ))}
    </div>
  );
}

function RiskBar({
  score,
  reasons,
  decision,
}: {
  score: number | null;
  reasons?: string | null;
  decision?: string | null;
}) {
  if (score === null) return <span className="text-[13px]" style={{ color: "#94A3B8" }}>N/A</span>;
  const pct      = Math.round(score * 100);
  const barColor = score > 0.7 ? "#FF4D4D" : score > 0.4 ? "#F59E0B" : "#10B981";
  const priority = getPriority(score, decision ?? null);
  return (
    <div className="min-w-[168px]">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-mono text-[13px] tabular-nums font-medium" style={{ color: barColor }}>
          {formatRiskScore(score)}
        </span>
        <span
          className="inline-flex items-center rounded px-1.5 py-[1px] text-[9px] font-semibold"
          style={{
            color: priority.color,
            background: priority.bg,
            border: `1px solid ${priority.border}`,
          }}
        >
          {priority.label}
        </span>
      </div>
      <div
        className="mt-1 h-1.5 w-14 overflow-hidden rounded-full"
        style={{ background: "rgba(255,255,255,0.07)" }}
      >
        <div
          className="h-full rounded-full"
          style={{ width: `${pct}%`, background: barColor, opacity: 0.80 }}
        />
      </div>
      <ReasonTags reasons={reasons} />
    </div>
  );
}

const COLUMNS = [
  { key: "case",   label: "Case"       },
  { key: "amount", label: "Amount"     },
  { key: "risk",   label: "Risk Score" },
  { key: "dec",    label: "Signal"     },
  { key: "status", label: "Verdict"    },
  { key: "time",   label: "Received"   },
  { key: "action", label: "Action"     },
];

interface ReviewQueueTableProps {
  rows: ReviewQueue;
}

function MobileCard({ row }: { row: ReviewQueue[number] }) {
  const isBlock = row.decision === "BLOCK";
  return (
    <div
      className="card p-4 space-y-3"
      style={isBlock ? { borderLeft: "3px solid rgba(255,77,77,0.55)" } : undefined}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[13px] font-semibold" style={{ color: "#8B949E" }}>
            #{row.id}
          </span>
          {isBlock && (
            <span
              className="rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wider"
              style={{ background: "rgba(255,77,77,0.12)", color: "#FF4D4D" }}
            >
              URGENT
            </span>
          )}
        </div>
        <div className="flex gap-2">
          {decisionBadge(row.decision)}
          {analystBadge(row.analyst_status)}
        </div>
      </div>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[20px] font-bold" style={{ color: "#F0F6FC" }}>
            {formatUSD(row.amount)}
          </p>
          <p className="mt-1 text-[12px]" style={{ color: "#4B5563" }}>
            {formatDateShort(row.timestamp)}
          </p>
        </div>
        <RiskBar score={row.risk_score} reasons={row.reasons} decision={row.decision} />
      </div>
      <CaseRowActions caseId={row.id} />
    </div>
  );
}

export function ReviewQueueTable({ rows }: ReviewQueueTableProps) {
  if (rows.length === 0) {
    return (
      <div className="card flex flex-col items-center justify-center gap-2 px-6 py-16">
        <p className="text-[14px] font-medium" style={{ color: "#8B949E" }}>
          Queue is clear
        </p>
        <p className="text-[13px]" style={{ color: "#4B5563" }}>
          No cases match the current filter. Select All Cases to view the full queue.
        </p>
      </div>
    );
  }

  const decisionRank: Record<string, number> = { BLOCK: 3, REVIEW: 2, APPROVE: 1 };
  const sortedRows = [...rows].sort((a, b) => {
    const riskDelta = (b.risk_score ?? -1) - (a.risk_score ?? -1);
    if (riskDelta !== 0) return riskDelta;
    return (decisionRank[b.decision ?? ""] ?? 0) - (decisionRank[a.decision ?? ""] ?? 0);
  });

  return (
    <>
      {/* Mobile: card-per-row */}
      <div className="space-y-3 md:hidden">
        {sortedRows.map((row) => (
          <MobileCard key={row.id} row={row} />
        ))}
      </div>

      {/* Desktop: table */}
      <div className="card hidden overflow-hidden md:block">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr
                style={{
                  background: "rgba(10,14,23,0.60)",
                  borderBottom: "1px solid rgba(255,255,255,0.09)",
                }}
              >
                {COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    className="whitespace-nowrap px-5 py-3.5 text-left table-header"
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row) => {
                const isBlock = row.decision === "BLOCK";
                return (
                  <tr
                    key={row.id}
                    style={{
                      borderBottom: "1px solid rgba(255,255,255,0.04)",
                      borderLeft: isBlock ? "3px solid rgba(251,113,133,0.38)" : "3px solid transparent",
                      background: isBlock ? "rgba(255,77,77,0.03)" : "transparent",
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLTableRowElement).style.borderBottom =
                        "1px solid rgba(148,163,184,0.12)";
                      (e.currentTarget as HTMLTableRowElement).style.borderLeft =
                        isBlock ? "3px solid rgba(251,113,133,0.58)" : "3px solid rgba(34,211,238,0.24)";
                      (e.currentTarget as HTMLTableRowElement).style.background =
                        isBlock ? "rgba(251,113,133,0.055)" : "rgba(34,211,238,0.035)";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLTableRowElement).style.borderBottom =
                        "1px solid rgba(255,255,255,0.04)";
                      (e.currentTarget as HTMLTableRowElement).style.borderLeft =
                        isBlock ? "3px solid rgba(251,113,133,0.38)" : "3px solid transparent";
                      (e.currentTarget as HTMLTableRowElement).style.background =
                        isBlock ? "rgba(255,77,77,0.03)" : "transparent";
                    }}
                  >
                    <td className="px-5 py-3.5">
                      <span className="font-mono text-[13px] font-medium" style={{ color: "#8B949E" }}>
                        #{row.id}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-5 py-3.5 text-[14px] font-bold" style={{ color: "#F0F6FC" }}>
                      {formatUSD(row.amount)}
                    </td>
                    <td className="px-5 py-3.5">
                      <RiskBar score={row.risk_score} reasons={row.reasons} decision={row.decision} />
                    </td>
                    <td className="px-5 py-3.5">{decisionBadge(row.decision)}</td>
                    <td className="px-5 py-3.5">{analystBadge(row.analyst_status)}</td>
                    <td className="whitespace-nowrap px-5 py-3.5 text-[13px]" style={{ color: "#4B5563" }}>
                      {formatDateShort(row.timestamp)}
                    </td>
                    <td className="px-5 py-3.5">
                      <CaseRowActions caseId={row.id} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
