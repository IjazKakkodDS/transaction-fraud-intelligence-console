"use client";

import { Receipt, ScanSearch, Workflow, Gavel } from "lucide-react";
import { type Prediction } from "@/types/case";
import { useWorkflowEvents } from "@/lib/hooks/useWorkflowEvents";
import { useInvestigation } from "@/lib/hooks/useInvestigation";
import { formatDateShort, formatLabel, sanitizeWorkflowMessage } from "@/lib/utils";

type TimelineEventType = "transaction" | "investigation" | "workflow" | "analyst";

interface TimelineEvent {
  id: string;
  type: TimelineEventType;
  timestamp: string;
  title: string;
  detail?: string;
}

const EVENT_META: Record<TimelineEventType, { label: string; icon: React.ReactNode; color: string }> = {
  transaction:   { label: "Transaction",  icon: <Receipt className="h-3.5 w-3.5" />,    color: "#22D3EE" },
  investigation: { label: "Investigation", icon: <ScanSearch className="h-3.5 w-3.5" />, color: "#A78BFA" },
  workflow:      { label: "Workflow",      icon: <Workflow className="h-3.5 w-3.5" />,   color: "#F59E0B" },
  analyst:       { label: "Analyst",       icon: <Gavel className="h-3.5 w-3.5" />,      color: "#10B981" },
};

interface CaseTimelineProps {
  caseData: Prediction;
  caseId: number;
}

export function CaseTimeline({ caseData, caseId }: CaseTimelineProps) {
  const { data: workflowEvents } = useWorkflowEvents(caseId);
  const { data: investigation } = useInvestigation(caseId);

  const events: TimelineEvent[] = [];

  if (caseData.timestamp) {
    events.push({
      id: "transaction",
      type: "transaction",
      timestamp: caseData.timestamp,
      title: "Transaction recorded",
      detail: "Original transaction time for this case.",
    });
  }

  if (investigation && "investigated_at" in investigation && investigation.investigated_at) {
    events.push({
      id: "investigation",
      type: "investigation",
      timestamp: investigation.investigated_at,
      title: "Investigation completed",
      detail: investigation.recommendation
        ? `Recommendation: ${formatLabel(investigation.recommendation)}`
        : undefined,
    });
  }

  if (workflowEvents) {
    for (const event of workflowEvents) {
      if (!event.created_at) continue;
      const parts: string[] = [];
      if (event.status) parts.push(formatLabel(event.status));
      if (event.source) parts.push(formatLabel(event.source));
      if (event.message) parts.push(sanitizeWorkflowMessage(event.message));
      events.push({
        id: `workflow-${event.id}`,
        type: "workflow",
        timestamp: event.created_at,
        title: `Workflow action: ${formatLabel(event.workflow_action)}`,
        detail: parts.length > 0 ? parts.join(" • ") : undefined,
      });
    }
  }

  if (caseData.reviewed_at) {
    events.push({
      id: "analyst",
      type: "analyst",
      timestamp: caseData.reviewed_at,
      title: "Analyst verdict recorded",
      detail: caseData.analyst_status ? `Status: ${formatLabel(caseData.analyst_status)}` : undefined,
    });
  }

  events.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  const distinctTypes = new Set(events.map((e) => e.type)).size;

  return (
    <section className="card overflow-hidden" aria-labelledby="case-timeline-heading">
      <div className="px-5 py-4">
        <p className="section-label">Lifecycle Summary</p>
        <h2 id="case-timeline-heading" className="mt-1 text-[16px] font-semibold" style={{ color: "#E5E7EB" }}>
          Case Timeline
        </h2>
        <p className="mt-1 text-[11px] leading-relaxed" style={{ color: "#6B7280" }}>
          High-level lifecycle view. See Automation Audit Trail for the detailed workflow log.
        </p>
      </div>

      {events.length === 0 && (
        <div className="px-5 pb-5">
          <p className="text-[13px]" style={{ color: "#6B7280" }}>
            No timeline events available for this case yet.
          </p>
        </div>
      )}

      {events.length > 0 && (
        <div className="px-5 pb-5">
          {distinctTypes <= 2 && (
            <p className="mb-3 text-[11px]" style={{ color: "#6B7280" }}>
              Partial lifecycle evidence: only {distinctTypes} of 4 event types are available for this case.
            </p>
          )}
          <ol className="space-y-0">
            {events.map((event, idx) => {
              const meta = EVENT_META[event.type];
              return (
                <li
                  key={event.id}
                  className="py-3"
                  style={{
                    borderTop: idx > 0 ? "1px solid rgba(255,255,255,0.05)" : undefined,
                  }}
                >
                  <div className="flex items-start gap-2">
                    <span className="mt-0.5 shrink-0" style={{ color: meta.color }}>
                      {meta.icon}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                        <span
                          className="min-w-0 break-words text-[13px] font-medium leading-snug"
                          style={{ color: "#C9D1D9" }}
                        >
                          {event.title}
                        </span>
                        <span className="shrink-0 font-mono text-[12px]" style={{ color: "#6B7280" }}>
                          {formatDateShort(event.timestamp)}
                        </span>
                      </div>
                      {event.detail && (
                        <p
                          className="mt-1 break-words text-[12px] leading-relaxed"
                          style={{ color: "#6B7280" }}
                        >
                          {event.detail}
                        </p>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </section>
  );
}
