"use client";

import { useState } from "react";
import { useReviewQueue } from "@/lib/hooks/useReviewQueue";
import { type AnalystStatus, type ReviewQueue } from "@/types/case";
import { QueueFilters } from "@/components/queue/QueueFilters";
import { ReviewQueueTable } from "@/components/queue/ReviewQueueTable";

function Skeleton() {
  return (
    <div className="card overflow-hidden">
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          className="h-12 animate-pulse"
          style={{
            borderBottom: "1px solid rgba(255,255,255,0.04)",
            background: i % 2 === 0 ? "rgba(255,255,255,0.025)" : "transparent",
          }}
        />
      ))}
    </div>
  );
}

function QueueStatusRail({ data }: { data: ReviewQueue }) {
  const p0Critical = data.filter(
    (r) => r.decision === "BLOCK" || (r.risk_score !== null && r.risk_score >= 0.85)
  ).length;
  const unreviewed = data.filter((r) => r.analyst_status === null).length;
  const reviewed   = data.filter((r) => r.analyst_status !== null).length;
  const falsePos   = data.filter((r) => r.analyst_status === "FALSE_POSITIVE").length;

  const cells = [
    { label: "TOTAL CASES",    value: data.length, color: "#C9D1D9" },
    { label: "P0 CRITICAL",    value: p0Critical,  color: p0Critical > 0 ? "#FF4D4D" : "#6B7280" },
    { label: "UNREVIEWED",     value: unreviewed,  color: unreviewed > 0 ? "#F59E0B" : "#6B7280" },
    { label: "REVIEWED",       value: reviewed,    color: reviewed > 0 ? "#10B981" : "#6B7280" },
    { label: "FALSE POSITIVE", value: falsePos,    color: falsePos > 0 ? "#22D3EE" : "#6B7280" },
  ];

  return (
    <div className="card overflow-hidden">
      <div className="grid grid-cols-3 sm:grid-cols-5">
        {cells.map((cell) => (
          <div
            key={cell.label}
            className="min-w-0 flex flex-col gap-1.5 px-4 py-3"
            style={{ borderRight: "1px solid rgba(255,255,255,0.05)" }}
          >
            <p
              className="font-mono font-semibold tabular-nums"
              style={{ fontSize: "18px", color: cell.color, letterSpacing: "-0.01em" }}
            >
              {cell.value}
            </p>
            <p className="metric-label">{cell.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function QueuePage() {
  const [selectedStatus, setSelectedStatus] = useState<AnalystStatus>(null);
  const filterParam = selectedStatus === null ? undefined : selectedStatus;

  const allCases                      = useReviewQueue(undefined);
  const { data, isLoading, isError }  = useReviewQueue(filterParam);

  return (
    <div className="mx-auto max-w-6xl space-y-4">

      {/* ── Hero ──────────────────────────────────────────── */}
      <div
        className="pb-4"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}
      >
        <p className="route-label mb-1.5">Analyst Workbench</p>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="page-hero-title">
            Review Queue
            {data && (
              <span className="ml-3 text-[16px] font-normal" style={{ color: "#4B5563" }}>
                {data.length} {data.length === 1 ? "case" : "cases"}
              </span>
            )}
          </h1>
          <span
            className="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold"
            style={{
              background: "rgba(16,185,129,0.08)",
              border: "1px solid rgba(16,185,129,0.22)",
              color: "#10B981",
            }}
          >
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: "#10B981" }} />
            LIVE
          </span>
        </div>
        <p
          className="mt-1 text-[13px] leading-relaxed"
          style={{ color: "#4B5563", maxWidth: "520px" }}
        >
          Prioritized fraud cases awaiting analyst review and verdict capture.
        </p>
      </div>

      {/* ── Queue Status Rail ─────────────────────────────── */}
      {allCases.data && <QueueStatusRail data={allCases.data} />}

      {/* ── Filters ───────────────────────────────────────── */}
      <QueueFilters selected={selectedStatus} onChange={setSelectedStatus} />

      {isError && (
        <div
          className="rounded-lg px-4 py-3 text-[13px]"
          style={{
            background: "rgba(255,77,77,0.07)",
            border: "1px solid rgba(255,77,77,0.22)",
            color: "#FF4D4D",
          }}
        >
          Could not load review queue. Check API connectivity.
        </div>
      )}

      {isLoading && <Skeleton />}
      {data && <ReviewQueueTable rows={data} />}

    </div>
  );
}
