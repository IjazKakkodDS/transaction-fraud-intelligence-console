"use client";

import { useState, useEffect } from "react";
import { useInvestigation } from "@/lib/hooks/useInvestigation";
import { useTriggerInvestigation } from "@/lib/hooks/useTriggerInvestigation";
import { type InvestigationReport } from "@/types/investigation";
import { InvestigationTrigger } from "@/components/cases/InvestigationTrigger";
import { formatDateShort } from "@/lib/utils";

const POLLING_WINDOW_MS = 3 * 60 * 1000;

function normalizeStringList(value: string | string[] | null | undefined): string[] {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) return parsed as string[];
  } catch { /* not JSON */ }
  return [value];
}

function toTitleCase(s: string): string {
  return s
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const REC_LABELS: Record<string, string> = {
  CONFIRM_FRAUD:  "Confirm Fraud",
  FALSE_POSITIVE: "False Positive",
  ESCALATE:       "Escalate",
};

function RecBadge({ value }: { value: string | null }) {
  if (!value) return null;
  const styles: Record<string, React.CSSProperties> = {
    CONFIRM_FRAUD:  { color: "#FF4D4D", background: "rgba(255,77,77,0.10)",   border: "1px solid rgba(255,77,77,0.28)"   },
    FALSE_POSITIVE: { color: "#22D3EE", background: "rgba(34,211,238,0.10)",  border: "1px solid rgba(34,211,238,0.28)"  },
    ESCALATE:       { color: "#F59E0B", background: "rgba(245,158,11,0.10)",  border: "1px solid rgba(245,158,11,0.28)"  },
  };
  return (
    <span
      className="inline-flex items-center rounded-md px-3 py-1.5 text-[13px] font-semibold tracking-wide"
      style={styles[value] ?? { color: "#8B949E", background: "rgba(139,148,158,0.10)", border: "1px solid rgba(139,148,158,0.20)" }}
    >
      {REC_LABELS[value] ?? toTitleCase(value)}
    </span>
  );
}

function ConfBadge({ value }: { value: string | null }) {
  if (!value) return null;
  const styles: Record<string, React.CSSProperties> = {
    HIGH:   { color: "#10B981", background: "rgba(16,185,129,0.10)",  border: "1px solid rgba(16,185,129,0.28)"  },
    MEDIUM: { color: "#F59E0B", background: "rgba(245,158,11,0.10)",  border: "1px solid rgba(245,158,11,0.28)"  },
    LOW:    { color: "#8B949E", background: "rgba(139,148,158,0.10)", border: "1px solid rgba(139,148,158,0.20)" },
  };
  return (
    <span
      className="inline-flex items-center rounded-md px-3 py-1.5 text-[13px] font-semibold"
      style={styles[value] ?? { color: "#8B949E" }}
    >
      {value} CONFIDENCE
    </span>
  );
}

function TagList({ items }: { items: string[] }) {
  if (items.length === 0) return <span style={{ color: "#4B5563" }}>None</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((item, i) => (
        <span
          key={i}
          className="inline-flex items-center rounded px-1.5 py-[1px] text-[11px] font-medium leading-5"
          style={{
            background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.07)",
            color: "#94A3B8",
          }}
        >
          {toTitleCase(item)}
        </span>
      ))}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div
      className="grid grid-cols-3 gap-4 py-2.5"
      style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
    >
      <dt className="section-label pt-0.5">{label}</dt>
      <dd className="col-span-2 text-[13px]" style={{ color: "#C9D1D9" }}>
        {children}
      </dd>
    </div>
  );
}

function ordinalSuffix(n: number): string {
  const abs = Math.abs(n);
  if (abs % 100 >= 11 && abs % 100 <= 13) return `${n}th`;
  switch (abs % 10) {
    case 1:  return `${n}st`;
    case 2:  return `${n}nd`;
    case 3:  return `${n}rd`;
    default: return `${n}th`;
  }
}

function DeterministicContext({ report }: { report: InvestigationReport }) {
  const hasContext =
    report.transaction_count_30d !== null ||
    report.amount_percentile !== null ||
    report.merchant_seen_before !== null;

  if (!hasContext) return null;

  const cells: { label: string; value: string | null }[] = [
    {
      label: "30D Transactions",
      value: report.transaction_count_30d !== null
        ? String(report.transaction_count_30d)
        : null,
    },
    {
      label: "Amount Percentile",
      value: report.amount_percentile !== null
        ? `${ordinalSuffix(Math.round(report.amount_percentile * 100))} pct.`
        : null,
    },
    {
      label: "Merchant",
      value: report.merchant_seen_before !== null
        ? (report.merchant_seen_before ? "Known" : "First-time")
        : null,
    },
  ];

  return (
    <div
      className="grid grid-cols-3 overflow-hidden rounded-md"
      style={{ border: "1px solid rgba(255,255,255,0.07)" }}
    >
      {cells.map((cell) => (
        <div
          key={cell.label}
          className="px-3 py-2.5"
          style={{ borderRight: "1px solid rgba(255,255,255,0.06)" }}
        >
          <p
            className="font-mono text-[15px] font-semibold tabular-nums"
            style={{ color: cell.value ? "#CBD5E1" : "#4B5563" }}
          >
            {cell.value ?? "—"}
          </p>
          <p
            className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.12em]"
            style={{ color: "#6B7280" }}
          >
            {cell.label}
          </p>
        </div>
      ))}
    </div>
  );
}

function CompleteReport({
  report,
  caseId,
  reviewedAt,
}: {
  report: InvestigationReport;
  caseId: number;
  reviewedAt?: string | null;
}) {
  // Show a timing notice when the investigation was generated after the analyst
  // verdict was already recorded — the verdict was made without AI input.
  const isPostVerdictInvestigation = (() => {
    if (!reviewedAt || !report.investigated_at) return false;
    try {
      return new Date(reviewedAt) < new Date(report.investigated_at);
    } catch {
      return false;
    }
  })();

  return (
    <div className="space-y-4">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <RecBadge value={report.recommendation} />
          <ConfBadge value={report.confidence} />
        </div>

        <div
          className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px]"
          style={{ color: "#6B7280" }}
        >
          {report.investigated_at && (
            <span>Investigated {formatDateShort(report.investigated_at)}</span>
          )}
          {report.agent_version && (
            <span style={{ color: "#4B5563" }}>
              Pipeline v{report.agent_version}
            </span>
          )}
        </div>

        {isPostVerdictInvestigation && (
          <p className="mt-1 text-[11px]" style={{ color: "#6B7280" }}>
            Note: This investigation was generated after the analyst verdict was recorded.
          </p>
        )}
      </div>

      <DeterministicContext report={report} />

      {report.summary && (
        <p className="text-[13px] leading-relaxed" style={{ color: "#8B949E" }}>
          {report.summary}
        </p>
      )}

      <dl style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }}>
        <Row label="Risk Factors">
          <TagList items={normalizeStringList(report.risk_factors)} />
        </Row>
        <Row label="Mitigating Factors">
          <TagList items={normalizeStringList(report.mitigating_factors)} />
        </Row>
        <Row label="Rules Triggered">
          <TagList items={normalizeStringList(report.rules_triggered)} />
        </Row>
        <Row label="Playbooks">
          <TagList items={normalizeStringList(report.playbooks_referenced)} />
        </Row>
        <Row label="Policies">
          <TagList items={normalizeStringList(report.policies_referenced)} />
        </Row>
        {report.recommendation_rationale && (
          <Row label="Rationale">
            <span className="text-[13px] leading-relaxed" style={{ color: "#8B949E" }}>
              {report.recommendation_rationale}
            </span>
          </Row>
        )}
        {report.confidence_rationale && (
          <Row label="Confidence Rationale">
            <span className="text-[13px] leading-relaxed" style={{ color: "#8B949E" }}>
              {report.confidence_rationale}
            </span>
          </Row>
        )}
      </dl>

      <div className="pt-2" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
        <InvestigationTrigger caseId={caseId} label="Re-run Investigation" />
      </div>
    </div>
  );
}

interface InvestigationPanelProps {
  caseId: number;
  reviewedAt?: string | null;
}

export function InvestigationPanel({ caseId, reviewedAt }: InvestigationPanelProps) {
  const [pollingUntil, setPollingUntil] = useState<number | null>(null);
  const { data, isLoading } = useInvestigation(caseId, pollingUntil);
  const { mutate, isPending, isError, error } = useTriggerInvestigation(caseId);

  // Reset pollingUntil when the window expires so the empty state reappears.
  // Math.max(0, remaining) handles the already-expired case without a synchronous setState.
  useEffect(() => {
    if (pollingUntil === null) return;
    const remaining = pollingUntil - Date.now();
    const timer = setTimeout(() => setPollingUntil(null), Math.max(0, remaining));
    return () => clearTimeout(timer);
  }, [pollingUntil]);

  function handleTrigger() {
    mutate(undefined, {
      onSuccess: () => setPollingUntil(Date.now() + POLLING_WINDOW_MS),
    });
  }

  const isComplete = data && data.status === "COMPLETE";
  const isWithinPollingWindow = data === null && pollingUntil !== null;

  return (
    <div
      className="card p-5"
      style={
        isComplete
          ? { borderTop: "3px solid rgba(34,211,238,0.45)" }
          : undefined
      }
    >
      <p className="section-label mb-4">AI Investigation Brief</p>

      {isLoading && (
        <p className="text-[13px]" style={{ color: "#4B5563" }}>
          Loading investigation...
        </p>
      )}

      {/* Post-trigger polling window: no DB row yet, Ollama is generating */}
      {!isLoading && isWithinPollingWindow && (
        <div className="flex items-center gap-3 text-[14px]" style={{ color: "#8B949E" }}>
          <span
            className="h-4 w-4 animate-spin rounded-full border-2"
            style={{ borderColor: "rgba(34,211,238,0.20)", borderTopColor: "#22D3EE" }}
          />
          Investigation request accepted. Generating analysis...
        </div>
      )}

      {/* No investigation and no active polling window */}
      {!isLoading && data === null && !isWithinPollingWindow && (
        <div className="space-y-4">
          <p className="text-[14px]" style={{ color: "#8B949E" }}>
            No investigation report for this case. Run the AI investigation to
            receive a structured analysis with risk factors, recommendation, and
            confidence level.
          </p>
          <div className="flex flex-col gap-2">
            <button
              onClick={handleTrigger}
              disabled={isPending}
              className="inline-flex w-fit items-center gap-2 rounded-md px-4 py-2 text-[13px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-35"
              style={{
                background: "rgba(34,211,238,0.10)",
                border: "1px solid rgba(34,211,238,0.28)",
                color: "#22D3EE",
                minHeight: "38px",
              }}
            >
              {isPending && (
                <span
                  className="h-3.5 w-3.5 animate-spin rounded-full border-2"
                  style={{ borderColor: "rgba(34,211,238,0.25)", borderTopColor: "#22D3EE" }}
                />
              )}
              {isPending ? "Starting..." : "Run AI Investigation"}
            </button>
            {isError && (
              <p className="text-[13px]" style={{ color: "#FF4D4D" }}>
                {error instanceof Error
                  ? error.message
                  : "Failed to trigger investigation. Try again."}
              </p>
            )}
          </div>
          <p className="text-[12px] leading-relaxed" style={{ color: "#6B7280" }}>
            Available in local full-stack runtime. Local LLM investigation brief
            generation is intentionally excluded from the hosted inspection profile.
          </p>
        </div>
      )}

      {/* Backend IN_PROGRESS row (normally unused — kept for safety) */}
      {data && data.status === "IN_PROGRESS" && (
        <div className="flex items-center gap-3 text-[14px]" style={{ color: "#8B949E" }}>
          <span
            className="h-4 w-4 animate-spin rounded-full border-2"
            style={{ borderColor: "rgba(34,211,238,0.20)", borderTopColor: "#22D3EE" }}
          />
          Generating investigation report...
        </div>
      )}

      {data && data.status === "FAILED" && (
        <div className="space-y-4">
          <div
            className="rounded-md px-4 py-3 text-[13px]"
            style={{
              background: "rgba(255,77,77,0.07)",
              border: "1px solid rgba(255,77,77,0.22)",
              color: "#FF4D4D",
            }}
          >
            Investigation failed.
            {"error_message" in data && data.error_message && (
              <span className="mt-1 block text-[12px] opacity-70">
                {data.error_message}
              </span>
            )}
          </div>
          <InvestigationTrigger caseId={caseId} label="Retry Investigation" />
          <p className="text-[12px] leading-relaxed" style={{ color: "#6B7280" }}>
            Available in local full-stack runtime. Local LLM investigation brief
            generation is intentionally excluded from the hosted inspection profile.
          </p>
        </div>
      )}

      {data && data.status === "COMPLETE" && (
        <CompleteReport
          report={data as InvestigationReport}
          caseId={caseId}
          reviewedAt={reviewedAt}
        />
      )}
    </div>
  );
}
