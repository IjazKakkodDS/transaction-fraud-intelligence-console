import Link from "next/link";
import { type WorkflowEvents } from "@/types/workflow";
import { formatDateShort, formatLabel } from "@/lib/utils";

interface WorkflowActivityFeedProps {
  events: WorkflowEvents;
}

function getSourceLabel(source: string) {
  const value = source.toLowerCase();
  if (value.includes("n8n")) return "Automation";
  if (value.includes("fastapi") || value.includes("api")) return "API";
  if (value.includes("manual")) return "Manual";
  return formatLabel(source);
}

export function WorkflowActivityFeed({ events }: WorkflowActivityFeedProps) {
  const recent = events.slice(0, 15);
  const successCount = recent.filter(
    (e) => e.status.toUpperCase() === "SUCCESS"
  ).length;

  return (
    <div className="card flex h-full flex-col">
      <div
        className="flex items-center justify-between px-5 py-3.5"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div className="flex items-center gap-2">
          <p className="section-label">Workflow Events</p>
          {recent.length > 0 && (
            <span
              className="rounded-full px-2 py-0.5 font-mono text-[10px] font-bold"
              style={{
                background: "rgba(34,211,238,0.08)",
                border: "1px solid rgba(34,211,238,0.18)",
                color: "#22D3EE",
              }}
            >
              {recent.length}
            </span>
          )}
        </div>
        <span
          className="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold"
          style={{
            background: "rgba(16,185,129,0.08)",
            border: "1px solid rgba(16,185,129,0.22)",
            color: "#10B981",
          }}
        >
          <span className="relative flex h-1.5 w-1.5">
            <span
              className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75"
              style={{ background: "#10B981" }}
            />
            <span
              className="relative inline-flex h-1.5 w-1.5 rounded-full"
              style={{ background: "#10B981" }}
            />
          </span>
          LIVE
        </span>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-2" style={{ maxHeight: "280px" }}>
        {recent.length === 0 ? (
          <p className="pt-4 text-[13px]" style={{ color: "#94A3B8" }}>
            No workflow events recorded.
          </p>
        ) : (
          <div className="pt-1">
            {recent.map((event) => {
              const isSuccess = event.status.toUpperCase() === "SUCCESS";
              return (
                <div
                  key={event.id}
                  className="grid grid-cols-[14px_minmax(0,1fr)_120px_112px] items-center gap-3 py-2.5"
                  style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
                >
                  <span className="relative flex h-2 w-2 shrink-0">
                    {isSuccess && (
                      <span
                        className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
                        style={{ background: "#10B981" }}
                      />
                    )}
                    <span
                      className="relative inline-flex h-2 w-2 rounded-full"
                      style={{ background: isSuccess ? "#10B981" : "#FF4D4D" }}
                    />
                  </span>

                  <span
                    className="min-w-0 truncate text-[13px] font-medium"
                    style={{ color: "#CBD5E1" }}
                  >
                    {formatLabel(event.workflow_action)}
                  </span>
                  <span className="truncate text-[12px]" style={{ color: "#94A3B8" }}>
                    {getSourceLabel(event.source)}
                  </span>
                  <span
                    className="shrink-0 text-right font-mono text-[12px]"
                    style={{ color: "#94A3B8" }}
                  >
                    {formatDateShort(event.created_at)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div
        className="shrink-0 flex items-center justify-between px-5 py-3"
        style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}
      >
        <span className="text-[11px]" style={{ color: "#94A3B8" }}>
          {successCount}/{recent.length} succeeded
        </span>
        <Link
          href="/workflow/events"
          className="text-[11px] font-semibold"
          style={{ color: "#22D3EE" }}
        >
          View all events
        </Link>
      </div>
    </div>
  );
}
