"use client";

import Link from "next/link";
import { useState } from "react";
import { useReviewCase } from "@/lib/hooks/useReviewCase";
import { type ReviewRequest } from "@/types/case";
import { formatDateShort } from "@/lib/utils";

const STATUS_OPTIONS: {
  value: ReviewRequest["analyst_status"];
  label: string;
  active: React.CSSProperties;
}[] = [
  {
    value: "CONFIRMED_FRAUD",
    label: "Confirmed Fraud",
    active: { color: "#FF4D4D", background: "rgba(255,77,77,0.12)", border: "2px solid rgba(255,77,77,0.45)" },
  },
  {
    value: "FALSE_POSITIVE",
    label: "False Positive",
    active: { color: "#22D3EE", background: "rgba(34,211,238,0.12)", border: "2px solid rgba(34,211,238,0.45)" },
  },
  {
    value: "APPROVED",
    label: "Approved",
    active: { color: "#10B981", background: "rgba(16,185,129,0.12)", border: "2px solid rgba(16,185,129,0.45)" },
  },
];

const INACTIVE_PILL: React.CSSProperties = {
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(255,255,255,0.09)",
  color: "#8B949E",
};

interface AnalystActionPanelProps {
  caseId: number;
  currentAnalystStatus: string | null;
  currentAnalystNotes: string | null;
  reviewedAt: string | null;
}

export function AnalystActionPanel({
  caseId,
  currentAnalystStatus,
  currentAnalystNotes,
  reviewedAt,
}: AnalystActionPanelProps) {
  const validStatuses = STATUS_OPTIONS.map((o) => o.value) as string[];
  const initialStatus =
    currentAnalystStatus && validStatuses.includes(currentAnalystStatus)
      ? (currentAnalystStatus as ReviewRequest["analyst_status"])
      : null;

  const [selectedStatus, setSelectedStatus] = useState<ReviewRequest["analyst_status"] | null>(initialStatus);
  const [notes, setNotes] = useState(currentAnalystNotes ?? "");
  const [saved, setSaved] = useState(false);

  const { mutate, isPending, isError, error } = useReviewCase(caseId);

  function handleSubmit() {
    if (!selectedStatus) return;
    setSaved(false);
    mutate(
      { analyst_status: selectedStatus, analyst_notes: notes.trim() || null },
      { onSuccess: () => setSaved(true) },
    );
  }

  const VERDICT_LABELS: Record<string, string> = {
    CONFIRMED_FRAUD: "CONFIRMED",
    FALSE_POSITIVE:  "FALSE POSITIVE",
    APPROVED:        "APPROVED",
  };
  const currentLabel = (currentAnalystStatus && VERDICT_LABELS[currentAnalystStatus]) ?? "UNREVIEWED";

  return (
    <div className="card p-5">
      <p className="section-label mb-1">Analyst Verdict</p>

      <p className="mb-4 text-[12px]" style={{ color: "#4B5563" }}>
        Select a verdict and submit. The decision is persisted with a timestamp and
        contributes to the operational audit record.
      </p>
      <div
        className="mb-5 flex flex-wrap items-center gap-3 rounded-md px-4 py-2.5 text-[13px]"
        style={{
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.07)",
        }}
      >
        <span style={{ color: "#4B5563" }}>Current verdict:</span>
        <span
          className="rounded-md px-2 py-0.5 text-[11px] font-semibold"
          style={{
            background: "rgba(139,148,158,0.10)",
            border: "1px solid rgba(139,148,158,0.20)",
            color: "#8B949E",
          }}
        >
          {currentLabel}
        </span>
        {reviewedAt && (
          <span style={{ color: "#4B5563" }}>
            Reviewed {formatDateShort(reviewedAt)}
          </span>
        )}
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}
        className="space-y-4"
      >
        <fieldset>
          <legend className="section-label mb-3">Select Verdict</legend>
          <div className="flex flex-wrap gap-2">
            {STATUS_OPTIONS.map(({ value, label, active }) => (
              <button
                key={value}
                type="button"
                onClick={() => { setSelectedStatus(value); setSaved(false); }}
                className="rounded-md px-4 py-2 text-[13px] font-medium transition-colors"
                style={selectedStatus === value ? active : INACTIVE_PILL}
              >
                {label}
              </button>
            ))}
          </div>
        </fieldset>

        <div>
          <label htmlFor="analyst-notes" className="section-label mb-2 block">
            Investigation Notes (optional)
          </label>
          <textarea
            id="analyst-notes"
            rows={3}
            value={notes}
            onChange={(e) => { setNotes(e.target.value); setSaved(false); }}
            placeholder="Add triage notes, investigation context, or supporting rationale..."
            className="w-full rounded-md px-3 py-2.5 text-[14px] placeholder:text-[#4B5563] focus:outline-none"
            style={{
              background: "rgba(10,14,23,0.60)",
              border: "1px solid rgba(255,255,255,0.09)",
              color: "#F0F6FC",
              lineHeight: "1.6",
            }}
          />
        </div>

        {saved && (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-[13px] font-medium" style={{ color: "#10B981" }}>
              Verdict recorded.
            </p>
            <Link
              href="/queue"
              className="rounded-md px-2.5 py-1 text-[12px] font-semibold"
              style={{
                color: "#22D3EE",
                background: "rgba(34,211,238,0.08)",
                border: "1px solid rgba(34,211,238,0.18)",
              }}
            >
              Back to Review Queue
            </Link>
          </div>
        )}
        {isError && (
          <p className="text-[13px]" style={{ color: "#FF4D4D" }}>
            {error instanceof Error ? error.message : "Failed to save review. Try again."}
          </p>
        )}

        <button
          type="submit"
          disabled={!selectedStatus || isPending}
          className="inline-flex items-center gap-2 rounded-md px-4 py-2.5 text-[13px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-35"
          style={{
            background: "rgba(34,211,238,0.10)",
            border: "1px solid rgba(34,211,238,0.28)",
            color: "#22D3EE",
            minHeight: "40px",
          }}
        >
          {isPending && (
            <span
              className="h-3.5 w-3.5 animate-spin rounded-full border-2"
              style={{ borderColor: "rgba(34,211,238,0.25)", borderTopColor: "#22D3EE" }}
            />
          )}
          {isPending ? "Submitting..." : "Submit Verdict"}
        </button>
      </form>
    </div>
  );
}
