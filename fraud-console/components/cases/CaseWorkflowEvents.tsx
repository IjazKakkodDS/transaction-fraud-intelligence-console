"use client";

import { useWorkflowEvents } from "@/lib/hooks/useWorkflowEvents";
import { formatDateShort, formatLabel, sanitizeWorkflowMessage } from "@/lib/utils";

const SOURCE_LABELS: Record<string, string> = {
  fastapi: "API",
  n8n: "Automation",
  manual: "Manual",
};

function StatusDot({ status }: { status: string }) {
  const upper = status.toUpperCase();
  const color =
    upper === "SUCCESS" ? "#10B981"
    : upper === "FAILED" ? "#FF4D4D"
    : "#8B949E";
  return (
    <span
      className="h-2 w-2 shrink-0 rounded-full"
      style={{ background: color }}
    />
  );
}

function SourceTag({ source }: { source: string }) {
  const styles: Record<string, React.CSSProperties> = {
    n8n:     { color: "#A78BFA", background: "rgba(167,139,250,0.08)", border: "1px solid rgba(167,139,250,0.22)" },
    fastapi: { color: "#22D3EE", background: "rgba(34,211,238,0.08)",  border: "1px solid rgba(34,211,238,0.22)"  },
    manual:  { color: "#8B949E", background: "rgba(139,148,158,0.08)", border: "1px solid rgba(139,148,158,0.18)" },
  };
  return (
    <span
      className="inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium"
      style={styles[source] ?? { color: "#8B949E" }}
    >
      {SOURCE_LABELS[source] ?? source}
    </span>
  );
}

function PriorityTag({ priority }: { priority: string | null }) {
  if (!priority) return null;
  const styles: Record<string, React.CSSProperties> = {
    HIGH:   { color: "#FF4D4D", background: "rgba(255,77,77,0.08)",   border: "1px solid rgba(255,77,77,0.22)"   },
    MEDIUM: { color: "#F59E0B", background: "rgba(245,158,11,0.08)",  border: "1px solid rgba(245,158,11,0.22)"  },
    LOW:    { color: "#8B949E", background: "rgba(139,148,158,0.08)", border: "1px solid rgba(139,148,158,0.18)" },
  };
  return (
    <span
      className="inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium"
      style={styles[priority.toUpperCase()] ?? { color: "#8B949E" }}
    >
      {formatLabel(priority)}
    </span>
  );
}

interface CaseWorkflowEventsProps {
  caseId: number;
}

export function CaseWorkflowEvents({ caseId }: CaseWorkflowEventsProps) {
  const { data, isLoading, isError } = useWorkflowEvents(caseId);

  if (isLoading) {
    return (
      <p className="text-[13px]" style={{ color: "#6B7280" }}>
        Loading automation events...
      </p>
    );
  }
  if (isError) {
    return (
      <p className="text-[13px]" style={{ color: "#FF4D4D" }}>
        Could not load automation events.
      </p>
    );
  }
  if (!data || data.length === 0) {
    return (
      <p className="text-[13px]" style={{ color: "#6B7280" }}>
        No automation events recorded for this case.
      </p>
    );
  }

  return (
    <div>
      {data.map((event, idx) => {
        const isFailed = event.status.toUpperCase() === "FAILED";
        return (
          <div
            key={event.id}
            className="py-3"
            style={{
              borderTop: idx > 0 ? "1px solid rgba(255,255,255,0.05)" : undefined,
              borderLeft: isFailed
                ? "2px solid rgba(255,77,77,0.40)"
                : "2px solid transparent",
              paddingLeft: "10px",
            }}
          >
            {/* Action name + timestamp */}
            <div className="flex items-start gap-2">
              <StatusDot status={event.status} />
              <span
                className="min-w-0 flex-1 text-[13px] font-medium leading-snug"
                style={{ color: isFailed ? "#FF4D4D" : "#C9D1D9" }}
              >
                {formatLabel(event.workflow_action)}
              </span>
              <span
                className="shrink-0 font-mono text-[12px]"
                style={{ color: "#6B7280" }}
              >
                {formatDateShort(event.created_at)}
              </span>
            </div>
            {/* Source + priority */}
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5 pl-4">
              <SourceTag source={event.source} />
              <PriorityTag priority={event.escalation_priority} />
            </div>
            {/* Message if present */}
            {event.message && (
              <p
                className="mt-1.5 pl-4 text-[12px] leading-relaxed"
                style={{ color: "#6B7280" }}
                title={sanitizeWorkflowMessage(event.message)}
              >
                {sanitizeWorkflowMessage(event.message)}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
