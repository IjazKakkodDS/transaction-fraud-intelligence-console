"use client";

import { useState } from "react";
import Link from "next/link";
import { type WorkflowEvents } from "@/types/workflow";
import { formatDateShort, formatLabel } from "@/lib/utils";

function StatusBadge({ status }: { status: string }) {
  const upper = status.toUpperCase();
  const style: React.CSSProperties =
    upper === "SUCCESS"
      ? { color: "#10B981", background: "rgba(16,185,129,0.10)",  border: "1px solid rgba(16,185,129,0.25)"  }
      : upper === "FAILED"
        ? { color: "#FF4D4D", background: "rgba(255,77,77,0.10)", border: "1px solid rgba(255,77,77,0.25)" }
        : { color: "#8B949E", background: "rgba(139,148,158,0.08)",border: "1px solid rgba(139,148,158,0.18)" };
  return (
    <span className="inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-semibold" style={style}>
      {formatLabel(status)}
    </span>
  );
}

function getSourceLabel(source: string): string {
  const lower = source.toLowerCase();
  if (lower.includes("n8n")) return "Automation";
  if (lower.includes("fastapi") || lower.includes("api")) return "API";
  if (lower.includes("manual")) return "Manual";
  return formatLabel(source);
}

function sanitizeMessage(msg: string): string {
  return msg.replace(/\bn8n\b/gi, "Automation");
}

function SourceBadge({ source }: { source: string }) {
  const styles: Record<string, React.CSSProperties> = {
    n8n:     { color: "#A78BFA", background: "rgba(167,139,250,0.08)", border: "1px solid rgba(167,139,250,0.22)" },
    fastapi: { color: "#22D3EE", background: "rgba(34,211,238,0.08)",  border: "1px solid rgba(34,211,238,0.22)"  },
    manual:  { color: "#8B949E", background: "rgba(139,148,158,0.08)", border: "1px solid rgba(139,148,158,0.18)" },
  };
  const lower = source.toLowerCase();
  const style =
    lower.includes("n8n")                          ? styles.n8n    :
    lower.includes("fastapi") || lower.includes("api") ? styles.fastapi :
    lower.includes("manual")                        ? styles.manual  :
    { color: "#8B949E" };
  return (
    <span className="inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium" style={style}>
      {getSourceLabel(source)}
    </span>
  );
}

function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return <span style={{ color: "#4B5563" }}>—</span>;
  const upper = priority.toUpperCase();
  const styles: Record<string, React.CSSProperties> = {
    HIGH:   { color: "#FF4D4D", background: "rgba(255,77,77,0.08)",   border: "1px solid rgba(255,77,77,0.22)"   },
    MEDIUM: { color: "#F59E0B", background: "rgba(245,158,11,0.08)",  border: "1px solid rgba(245,158,11,0.22)"  },
    LOW:    { color: "#8B949E", background: "rgba(139,148,158,0.08)", border: "1px solid rgba(139,148,158,0.18)" },
  };
  return (
    <span className="inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium"
      style={styles[upper] ?? { color: "#8B949E" }}>
      {formatLabel(priority)}
    </span>
  );
}

const STATUS_FILTERS = ["All", "SUCCESS", "FAILED"] as const;
const SOURCE_FILTERS = ["All", "n8n", "fastapi", "manual"] as const;
type StatusFilter = (typeof STATUS_FILTERS)[number];
type SourceFilter = (typeof SOURCE_FILTERS)[number];

const SOURCE_FILTER_LABELS: Record<string, string> = {
  All:     "All",
  n8n:     "Automation",
  fastapi: "API",
  manual:  "Manual",
};

const ACTIVE_FILTER: React.CSSProperties = {
  background: "rgba(34,211,238,0.10)",
  border: "1px solid rgba(34,211,238,0.28)",
  color: "#22D3EE",
};
const INACTIVE_FILTER: React.CSSProperties = {
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(255,255,255,0.08)",
  color: "#8B949E",
};

function FilterPills<T extends string>({
  label,
  options,
  selected,
  onChange,
  labelMap,
}: {
  label: string;
  options: readonly T[];
  selected: T;
  onChange: (v: T) => void;
  labelMap?: Record<string, string>;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="section-label">{label}</span>
      <div className="flex flex-wrap gap-1.5">
        {options.map((opt) => (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            className="rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors"
            style={selected === opt ? ACTIVE_FILTER : INACTIVE_FILTER}
          >
            {labelMap?.[opt] ?? opt}
          </button>
        ))}
      </div>
    </div>
  );
}

const COLUMNS = ["Case", "Time", "Action", "Status", "Source", "Priority", "Message"];

interface EventsTableProps {
  events: WorkflowEvents;
}

export function EventsTable({ events }: EventsTableProps) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("All");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("All");

  const filtered = events.filter((e) => {
    if (statusFilter !== "All" && e.status.toUpperCase() !== statusFilter) return false;
    if (sourceFilter !== "All" && e.source !== sourceFilter) return false;
    return true;
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-4">
        <FilterPills label="Status" options={STATUS_FILTERS} selected={statusFilter} onChange={setStatusFilter} />
        <FilterPills label="Source" options={SOURCE_FILTERS} selected={sourceFilter} onChange={setSourceFilter} labelMap={SOURCE_FILTER_LABELS} />
      </div>

      {filtered.length === 0 ? (
        <div className="card flex items-center justify-center px-6 py-16">
          <p className="text-[13px]" style={{ color: "#4B5563" }}>
            {events.length === 0 ? "No workflow events recorded yet." : "No events match the current filters."}
          </p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full table-fixed">
              <colgroup>
                <col style={{ width: "88px" }} />
                <col style={{ width: "132px" }} />
                <col style={{ width: "18%" }} />
                <col style={{ width: "96px" }} />
                <col style={{ width: "104px" }} />
                <col style={{ width: "96px" }} />
                <col />
              </colgroup>
              <thead>
                <tr style={{ background: "rgba(10,14,23,0.60)", borderBottom: "1px solid rgba(255,255,255,0.09)" }}>
                  {COLUMNS.map((col) => (
                    <th key={col} className="whitespace-nowrap px-5 py-3.5 text-left table-header">{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((event) => {
                  const isFailed = event.status.toUpperCase() === "FAILED";
                  const displayMessage = event.message ? sanitizeMessage(event.message) : null;
                  return (
                    <tr
                      key={event.id}
                      style={{
                        borderBottom: "1px solid rgba(255,255,255,0.04)",
                        background: isFailed ? "rgba(255,77,77,0.04)" : "transparent",
                        borderLeft: isFailed ? "2px solid rgba(255,77,77,0.38)" : undefined,
                      }}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLTableRowElement).style.background =
                          isFailed ? "rgba(255,77,77,0.07)" : "rgba(34,211,238,0.02)";
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLTableRowElement).style.background =
                          isFailed ? "rgba(255,77,77,0.04)" : "transparent";
                      }}
                    >
                      <td className="px-5 py-3">
                        {event.case_id !== null ? (
                          <Link href={`/cases/${event.case_id}`}
                            className="font-mono text-[13px] font-medium underline-offset-2 hover:underline"
                            style={{ color: "#22D3EE" }}>
                            #{event.case_id}
                          </Link>
                        ) : (
                          <span className="text-[12px]" style={{ color: "#4B5563" }}>—</span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-[12px]" style={{ color: "#6B7280" }}>
                        {formatDateShort(event.created_at)}
                      </td>
                      <td className="px-5 py-3 text-[13px] font-medium" style={{ color: "#C9D1D9" }}>
                        {formatLabel(event.workflow_action)}
                      </td>
                      <td className="px-5 py-3"><StatusBadge status={event.status} /></td>
                      <td className="px-5 py-3"><SourceBadge source={event.source} /></td>
                      <td className="px-5 py-3"><PriorityBadge priority={event.escalation_priority} /></td>
                      <td className="px-5 py-3 text-[12px]" style={{ color: "#4B5563" }}>
                        {displayMessage
                          ? <span className="line-clamp-2" title={displayMessage}>{displayMessage}</span>
                          : <span style={{ color: "#374151" }}>—</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
