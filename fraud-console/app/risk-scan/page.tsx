"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { exportRiskScanResults } from "@/lib/api/riskScan";
import {
  type RiskScanResult,
  type RiskScanStatus,
  type RiskScanSummary,
} from "@/types/riskScan";
import { ApiError } from "@/types/api";
import { useRiskScanUpload } from "@/lib/hooks/useRiskScanUpload";
import { useRiskScanStatus } from "@/lib/hooks/useRiskScanStatus";
import { useRiskScanSummary } from "@/lib/hooks/useRiskScanSummary";
import { useRiskScanResults } from "@/lib/hooks/useRiskScanResults";
import { useRiskScanPromote } from "@/lib/hooks/useRiskScanPromote";

// ─── Design constants ────────────────────────────────────────────────────────

const PRIORITY_STYLE: Record<string, { color: string; bg: string; border: string }> = {
  P0: { color: "#FF4D4D", bg: "rgba(255,77,77,0.10)",    border: "rgba(255,77,77,0.28)" },
  P1: { color: "#F59E0B", bg: "rgba(245,158,11,0.10)",   border: "rgba(245,158,11,0.28)" },
  P2: { color: "#22D3EE", bg: "rgba(34,211,238,0.10)",   border: "rgba(34,211,238,0.28)" },
  P3: { color: "#8B949E", bg: "rgba(139,148,158,0.10)",  border: "rgba(139,148,158,0.20)" },
};

const DECISION_COLOR: Record<string, string> = {
  BLOCK:   "#FF4D4D",
  REVIEW:  "#F59E0B",
  APPROVE: "#10B981",
};

const VSTATUS_COLOR: Record<string, string> = {
  VALID:   "#10B981",
  INVALID: "#FF4D4D",
  SKIPPED: "#F59E0B",
};

// ─── Formatting helpers ──────────────────────────────────────────────────────

function fmtCurrency(n: number | null): string {
  if (n === null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(n);
}

function fmtScore(n: number | null): string {
  if (n === null) return "—";
  return n.toFixed(3);
}

// Safely extracts top_risk_patterns from the flexible risk_summary field.
function extractPatterns(
  rs: Record<string, unknown> | null | undefined,
): Array<{ reason: string; count: number }> {
  if (!rs) return [];
  const raw = rs["top_risk_patterns"];
  if (!Array.isArray(raw)) return [];
  const out: Array<{ reason: string; count: number }> = [];
  for (const item of raw) {
    if (
      item !== null &&
      typeof item === "object" &&
      typeof (item as Record<string, unknown>).reason === "string" &&
      typeof (item as Record<string, unknown>).count === "number"
    ) {
      out.push(item as { reason: string; count: number });
    }
  }
  return out;
}

// ─── Shared micro-components ─────────────────────────────────────────────────

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      className="rounded-lg px-4 py-3 text-[13px]"
      style={{
        background: "rgba(255,77,77,0.07)",
        border: "1px solid rgba(255,77,77,0.22)",
        color: "#FF4D4D",
      }}
    >
      {message}
    </div>
  );
}

function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="card overflow-hidden">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-11 animate-pulse"
          style={{
            borderBottom: "1px solid rgba(255,255,255,0.04)",
            background: i % 2 === 0 ? "rgba(255,255,255,0.02)" : "transparent",
          }}
        />
      ))}
    </div>
  );
}

// ─── Validation strip ────────────────────────────────────────────────────────

type UploadCounts = {
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  skipped_rows: number;
};

function ValidationStrip({ data }: { data: UploadCounts }) {
  const cells = [
    { label: "Total Rows", value: data.total_rows,   color: "#C9D1D9" },
    { label: "Valid",      value: data.valid_rows,   color: "#10B981" },
    { label: "Invalid",    value: data.invalid_rows, color: data.invalid_rows > 0 ? "#FF4D4D" : "#6B7280" },
    { label: "Skipped",    value: data.skipped_rows, color: data.skipped_rows > 0 ? "#F59E0B" : "#6B7280" },
  ];
  return (
    <div className="card overflow-hidden">
      <div
        className="px-4 py-2.5"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <p className="section-label">CSV Validation</p>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4">
        {cells.map((c) => (
          <div
            key={c.label}
            className="px-4 py-3"
            style={{ borderRight: "1px solid rgba(255,255,255,0.05)" }}
          >
            <p
              className="text-[22px] font-semibold tabular-nums leading-none"
              style={{ color: c.color }}
            >
              {c.value}
            </p>
            <p className="mt-1.5 metric-label">{c.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function statusLabel(status: RiskScanStatus["status"]): string {
  switch (status) {
    case "QUEUED":
      return "Queued";
    case "PROCESSING":
      return "Processing";
    case "COMPLETE":
      return "Complete";
    case "FAILED":
      return "Failed";
    case "CANCELLED":
      return "Cancelled";
  }
}

function ProgressCard({ status }: { status: RiskScanStatus }) {
  const pct = Math.max(0, Math.min(100, status.progress_percent ?? 0));
  const badgeColor =
    status.status === "FAILED"
      ? "#FF4D4D"
      : status.status === "COMPLETE"
      ? "#10B981"
      : status.status === "CANCELLED"
      ? "#8B949E"
      : "#22D3EE";
  const cells = [
    { label: "Processed", value: `${status.processed_rows} / ${status.total_rows}` },
    { label: "Valid", value: String(status.valid_rows) },
    { label: "Invalid", value: String(status.invalid_rows) },
    { label: "Skipped", value: String(status.skipped_rows) },
    { label: "P0", value: String(status.p0_count) },
    { label: "P1", value: String(status.p1_count) },
  ];

  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="section-label">Scanning portfolio rows</p>
          <p className="mt-1 text-[12px]" style={{ color: "#6B7280" }}>
            Live job progress updates from the async risk scan engine.
          </p>
        </div>
        <span
          className="rounded px-2.5 py-1 font-mono text-[11px] font-bold"
          style={{
            color: badgeColor,
            background: `${badgeColor}14`,
            border: `1px solid ${badgeColor}38`,
          }}
        >
          {statusLabel(status.status)}
        </span>
      </div>

      <div className="mt-4">
        <div className="mb-1.5 flex items-center justify-between">
          <span className="font-mono text-[11px]" style={{ color: "#8B949E" }}>
            {status.processed_rows} / {status.total_rows} rows
          </span>
          <span className="font-mono text-[11px] font-semibold" style={{ color: badgeColor }}>
            {Math.round(pct)}%
          </span>
        </div>
        <div
          className="h-2 overflow-hidden rounded-full"
          style={{ background: "rgba(255,255,255,0.06)" }}
        >
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${pct}%`,
              background: badgeColor,
            }}
          />
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {cells.map((cell) => (
          <div
            key={cell.label}
            className="rounded px-3 py-2"
            style={{
              background: "rgba(255,255,255,0.025)",
              border: "1px solid rgba(255,255,255,0.07)",
            }}
          >
            <p className="font-mono text-[13px] font-semibold tabular-nums" style={{ color: "#C9D1D9" }}>
              {cell.value}
            </p>
            <p className="mt-1 metric-label">{cell.label}</p>
          </div>
        ))}
      </div>

      {status.status === "FAILED" && status.error_message && (
        <div className="mt-3">
          <ErrorBanner message={status.error_message} />
        </div>
      )}
    </div>
  );
}

// ─── Portfolio KPI rail ──────────────────────────────────────────────────────

function PortfolioKPIs({ summary }: { summary: RiskScanSummary }) {
  const atRisk =
    summary.exposure.critical_amount + summary.exposure.high_amount;
  const cells = [
    {
      label: "Total Scored",
      value: String(summary.valid_rows),
      color: "#C9D1D9",
    },
    {
      label: "P0 Critical",
      value: String(summary.tier_distribution.critical),
      color: summary.tier_distribution.critical > 0 ? "#FF4D4D" : "#6B7280",
    },
    {
      label: "P1 High",
      value: String(summary.tier_distribution.high),
      color: summary.tier_distribution.high > 0 ? "#F59E0B" : "#6B7280",
    },
    {
      label: "Exposure at Risk",
      value: fmtCurrency(atRisk),
      color: atRisk > 0 ? "#FF4D4D" : "#6B7280",
    },
  ];
  return (
    <div className="card overflow-hidden">
      <div className="grid grid-cols-2 sm:grid-cols-4">
        {cells.map((c) => (
          <div
            key={c.label}
            className="px-4 py-3"
            style={{ borderRight: "1px solid rgba(255,255,255,0.05)" }}
          >
            <p
              className="text-[22px] font-semibold tabular-nums leading-none"
              style={{ color: c.color }}
            >
              {c.value}
            </p>
            <p className="mt-1.5 metric-label">{c.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Tier distribution ───────────────────────────────────────────────────────

function TierDistribution({ summary }: { summary: RiskScanSummary }) {
  const total = Math.max(summary.valid_rows, 1);
  const rows = [
    { label: "Critical", p: "P0", count: summary.tier_distribution.critical },
    { label: "High",     p: "P1", count: summary.tier_distribution.high },
    { label: "Medium",   p: "P2", count: summary.tier_distribution.medium },
    { label: "Low",      p: "P3", count: summary.tier_distribution.low },
  ];
  return (
    <div className="card p-4">
      <p className="section-label mb-3">Tier Distribution</p>
      <div className="space-y-2.5">
        {rows.map((r) => {
          const pct = (r.count / total) * 100;
          const ps = PRIORITY_STYLE[r.p];
          return (
            <div key={r.label}>
              <div className="mb-1 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span
                    className="rounded px-1.5 py-0.5 font-mono text-[10px] font-bold"
                    style={{
                      color: ps.color,
                      background: ps.bg,
                      border: `1px solid ${ps.border}`,
                    }}
                  >
                    {r.p}
                  </span>
                  <span className="text-[12px]" style={{ color: "#8B949E" }}>
                    {r.label}
                  </span>
                </div>
                <span
                  className="font-mono text-[12px] font-semibold tabular-nums"
                  style={{ color: r.count > 0 ? ps.color : "#374151" }}
                >
                  {r.count}
                </span>
              </div>
              <div
                className="h-1 overflow-hidden rounded-full"
                style={{ background: "rgba(255,255,255,0.06)" }}
              >
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${pct}%`,
                    background: ps.color,
                    opacity: r.count > 0 ? 0.7 : 0,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Exposure panel ──────────────────────────────────────────────────────────

function ExposurePanel({ summary }: { summary: RiskScanSummary }) {
  const { total_amount, critical_amount, high_amount } = summary.exposure;
  const critPct =
    total_amount > 0
      ? Math.round((critical_amount / total_amount) * 100)
      : 0;
  return (
    <div className="card p-4">
      <p className="section-label mb-3">Exposure Concentration</p>
      <div className="space-y-2.5">
        {[
          { label: "Total Amount",      value: total_amount,    color: "#C9D1D9" },
          { label: "Critical Exposure", value: critical_amount, color: "#FF4D4D" },
          { label: "High Exposure",     value: high_amount,     color: "#F59E0B" },
        ].map(({ label, value, color }) => (
          <div key={label} className="flex items-center justify-between">
            <span className="text-[12px]" style={{ color: "#8B949E" }}>
              {label}
            </span>
            <span
              className="font-mono text-[13px] font-semibold tabular-nums"
              style={{ color }}
            >
              {fmtCurrency(value)}
            </span>
          </div>
        ))}
        {total_amount > 0 && critical_amount > 0 && (
          <div
            className="rounded px-3 py-2 text-[11px]"
            style={{
              background: "rgba(255,77,77,0.06)",
              border: "1px solid rgba(255,77,77,0.16)",
              color: "#FF8080",
            }}
          >
            {critPct}% of portfolio in critical risk tier
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Risk patterns ───────────────────────────────────────────────────────────

function RiskPatterns({ summary }: { summary: RiskScanSummary }) {
  const patterns = extractPatterns(summary.risk_summary);
  return (
    <div className="card p-4">
      <p className="section-label mb-3">Top Risk Patterns</p>
      {patterns.length === 0 ? (
        <p className="text-[12px]" style={{ color: "#6B7280" }}>
          No risk patterns recorded.
        </p>
      ) : (
        <div className="space-y-1.5">
          {patterns.slice(0, 5).map((p) => (
            <div key={p.reason} className="flex items-center justify-between gap-2">
              <span
                className="rounded px-2 py-1 text-[11px] font-medium leading-none"
                style={{
                  background: "rgba(255,77,77,0.08)",
                  border: "1px solid rgba(255,77,77,0.16)",
                  color: "#FF8080",
                }}
              >
                {p.reason}
              </span>
              <span
                className="shrink-0 font-mono text-[11px] tabular-nums"
                style={{ color: "#6B7280" }}
              >
                ×{p.count}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Reasons cell ────────────────────────────────────────────────────────────

function ReasonsCell({ reasons }: { reasons: string | null }) {
  if (!reasons) return <span style={{ color: "#374151" }}>—</span>;
  const parts = reasons
    .split("|")
    .map((s) => s.trim())
    .filter(Boolean);
  if (parts.length === 0) return <span style={{ color: "#374151" }}>—</span>;
  const extra = parts.length - 1;
  return (
    <span
      className="text-[11px]"
      style={{ color: "#8B949E" }}
      title={reasons}
    >
      {parts[0]}
      {extra > 0 && (
        <span className="ml-1 font-semibold" style={{ color: "#6B7280" }}>
          +{extra}
        </span>
      )}
    </span>
  );
}

// ─── Results table ───────────────────────────────────────────────────────────

function ResultsTable({
  rows,
  pendingId,
  onPromote,
}: {
  rows: RiskScanResult[];
  pendingId: number | null;
  onPromote: (row: RiskScanResult) => void;
}) {
  if (rows.length === 0) {
    return (
      <div
        className="card flex items-center justify-center py-10 text-[13px]"
        style={{ color: "#6B7280" }}
      >
        No results match the current filter.
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table
          style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}
        >
          <thead>
            <tr style={{ background: "rgba(0,0,0,0.20)" }}>
              {[
                "Priority", "Row", "Transaction ID", "Amount",
                "Country", "Payment Method", "Risk Score",
                "Decision", "Reasons", "Status", "Promotion",
              ].map((col, i) => (
                <th
                  key={col}
                  style={{
                    padding: "8px 12px",
                    textAlign: i === 3 || i === 6 ? "right" : "left",
                    fontSize: "10px",
                    fontWeight: 600,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    color: "#6B7280",
                    borderBottom: "1px solid rgba(255,255,255,0.07)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => {
              const ps = row.operational_priority
                ? PRIORITY_STYLE[row.operational_priority]
                : null;
              const decColor = row.decision
                ? DECISION_COLOR[row.decision]
                : "#6B7280";
              const vsColor =
                VSTATUS_COLOR[row.validation_status] ?? "#8B949E";
              const isPromoting = pendingId === row.id;
              const rowBg =
                idx % 2 === 0
                  ? "rgba(255,255,255,0.015)"
                  : "transparent";

              return (
                <tr
                  key={row.id}
                  style={{
                    background: rowBg,
                    borderBottom: "1px solid rgba(255,255,255,0.04)",
                  }}
                >
                  {/* Priority */}
                  <td style={{ padding: "8px 12px" }}>
                    {ps ? (
                      <span
                        className="inline-flex items-center rounded px-1.5 py-0.5 font-mono text-[10px] font-bold"
                        style={{
                          color: ps.color,
                          background: ps.bg,
                          border: `1px solid ${ps.border}`,
                        }}
                      >
                        {row.operational_priority}
                      </span>
                    ) : (
                      <span style={{ color: "#374151" }}>—</span>
                    )}
                  </td>

                  {/* Row # */}
                  <td
                    style={{
                      padding: "8px 12px",
                      color: "#6B7280",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {row.row_number}
                  </td>

                  {/* Transaction ID */}
                  <td style={{ padding: "8px 12px", maxWidth: "140px" }}>
                    <span
                      className="block truncate font-mono text-[11px]"
                      style={{ color: "#C9D1D9" }}
                      title={row.transaction_id ?? ""}
                    >
                      {row.transaction_id ?? "—"}
                    </span>
                  </td>

                  {/* Amount */}
                  <td
                    style={{
                      padding: "8px 12px",
                      textAlign: "right",
                      color: "#C9D1D9",
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {fmtCurrency(row.amount)}
                  </td>

                  {/* Country */}
                  <td style={{ padding: "8px 12px", color: "#8B949E" }}>
                    {row.country ?? "—"}
                  </td>

                  {/* Payment Method */}
                  <td style={{ padding: "8px 12px", color: "#8B949E", maxWidth: "120px" }}>
                    <span className="block truncate" title={row.payment_method ?? ""}>
                      {row.payment_method ?? "—"}
                    </span>
                  </td>

                  {/* Risk Score */}
                  <td style={{ padding: "8px 12px", textAlign: "right" }}>
                    {row.risk_score !== null ? (
                      <span
                        className="font-mono tabular-nums"
                        style={{
                          color:
                            row.risk_score >= 0.8
                              ? "#FF4D4D"
                              : row.risk_score >= 0.6
                              ? "#F59E0B"
                              : "#8B949E",
                        }}
                      >
                        {fmtScore(row.risk_score)}
                      </span>
                    ) : (
                      <span style={{ color: "#374151" }}>—</span>
                    )}
                  </td>

                  {/* Decision */}
                  <td style={{ padding: "8px 12px" }}>
                    {row.decision ? (
                      <span
                        className="font-mono text-[10px] font-bold"
                        style={{ color: decColor }}
                      >
                        {row.decision}
                      </span>
                    ) : (
                      <span style={{ color: "#374151" }}>—</span>
                    )}
                  </td>

                  {/* Reasons / validation errors */}
                  <td style={{ padding: "8px 12px", maxWidth: "180px" }}>
                    {row.validation_status === "VALID" ? (
                      <ReasonsCell reasons={row.reasons} />
                    ) : (
                      <span
                        className="text-[11px]"
                        style={{ color: "#6B7280" }}
                        title={row.validation_errors?.join(", ") ?? ""}
                      >
                        {row.validation_errors?.[0] ?? row.validation_status}
                      </span>
                    )}
                  </td>

                  {/* Validation status */}
                  <td style={{ padding: "8px 12px" }}>
                    <span
                      className="font-mono text-[10px] font-bold"
                      style={{ color: vsColor }}
                    >
                      {row.validation_status}
                    </span>
                  </td>

                  {/* Promotion */}
                  <td style={{ padding: "8px 12px", whiteSpace: "nowrap" }}>
                    {row.validation_status === "VALID" && row.promoted ? (
                      <Link
                        href={`/cases/${row.promoted_case_id}`}
                        className="text-[11px] font-semibold"
                        style={{ color: "#10B981" }}
                      >
                        Case #{row.promoted_case_id}
                      </Link>
                    ) : row.validation_status === "VALID" ? (
                      <button
                        type="button"
                        onClick={() => onPromote(row)}
                        disabled={isPromoting}
                        className="rounded px-2 py-1 text-[11px] font-semibold"
                        style={{
                          background: "rgba(34,211,238,0.08)",
                          border: "1px solid rgba(34,211,238,0.22)",
                          color: "#22D3EE",
                          opacity: isPromoting ? 0.5 : 1,
                          cursor: isPromoting ? "not-allowed" : "pointer",
                        }}
                      >
                        {isPromoting ? "…" : "Promote"}
                      </button>
                    ) : (
                      <span style={{ color: "#374151" }}>—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Tier filter tabs ────────────────────────────────────────────────────────

type TierFilter = "P0" | "P1" | "P2" | "P3" | undefined;

const TIER_TABS: Array<{ label: string; value: TierFilter }> = [
  { label: "All", value: undefined },
  { label: "P0",  value: "P0" },
  { label: "P1",  value: "P1" },
  { label: "P2",  value: "P2" },
  { label: "P3",  value: "P3" },
];

function PaginationControls({
  page,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}) {
  if (totalItems === 0) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, totalItems);
  const buttonStyle = (disabled: boolean) => ({
    background: disabled ? "rgba(255,255,255,0.025)" : "rgba(255,255,255,0.05)",
    border: "1px solid rgba(255,255,255,0.09)",
    color: disabled ? "#4B5563" : "#C9D1D9",
    cursor: disabled ? "not-allowed" : "pointer",
  });

  return (
    <div
      className="flex flex-wrap items-center justify-between gap-3 rounded-lg px-3 py-2"
      style={{
        background: "rgba(255,255,255,0.018)",
        border: "1px solid rgba(255,255,255,0.07)",
      }}
    >
      <p className="text-[12px]" style={{ color: "#8B949E" }}>
        Showing {start}-{end} of {totalItems} results
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          className="rounded px-3 py-1.5 text-[12px] font-semibold"
          style={buttonStyle(page <= 1)}
        >
          Previous
        </button>
        <span className="font-mono text-[12px]" style={{ color: "#6B7280" }}>
          Page {page} / {Math.max(totalPages, 1)}
        </span>
        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          className="rounded px-3 py-1.5 text-[12px] font-semibold"
          style={buttonStyle(page >= totalPages)}
        >
          Next
        </button>
      </div>
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function RiskScanPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile]       = useState<File | null>(null);
  const [scanId, setScanId]                   = useState<string | null>(null);
  const [tierFilter, setTierFilter]           = useState<TierFilter>(undefined);
  const [resultsPage, setResultsPage]         = useState(1);
  const [pendingPromoteId, setPendingPromoteId] = useState<number | null>(null);
  const [promoteError, setPromoteError]       = useState<string | null>(null);
  const [exportError, setExportError]         = useState<string | null>(null);

  const upload  = useRiskScanUpload();
  const status = useRiskScanStatus(scanId ?? undefined);
  const statusData = status.data;
  const isComplete = statusData?.status === "COMPLETE";
  const summary = useRiskScanSummary(scanId ?? undefined, isComplete);
  const results = useRiskScanResults(
    scanId ?? undefined,
    tierFilter ? { tier: tierFilter } : undefined,
    resultsPage,
    100,
    isComplete,
  );
  const promote = useRiskScanPromote();

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setSelectedFile(e.target.files?.[0] ?? null);
  }

  async function handleUpload() {
    if (!selectedFile) return;
    setPromoteError(null);
    setExportError(null);
    try {
      const r = await upload.mutateAsync(selectedFile);
      setScanId(r.scan_id);
      setTierFilter(undefined);
      setResultsPage(1);
    } catch {
      // error surfaced via upload.error below
    }
  }

  async function handlePromote(row: RiskScanResult) {
    if (!scanId || !isComplete) return;
    setPendingPromoteId(row.id);
    setPromoteError(null);
    try {
      await promote.mutateAsync({ scanId, resultId: row.id });
      await Promise.all([summary.refetch(), results.refetch()]);
    } catch (err) {
      setPromoteError(
        err instanceof ApiError
          ? err.detail
          : "Promotion failed. Please try again.",
      );
    } finally {
      setPendingPromoteId(null);
    }
  }

  async function handleExport() {
    if (!scanId || !isComplete) return;
    setExportError(null);
    try {
      const blob = await exportRiskScanResults(scanId);
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = `risk-scan-${scanId.slice(0, 8)}-results.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(
        err instanceof ApiError
          ? err.detail
          : "Export failed. Please try again.",
      );
    }
  }

  const uploadError =
    upload.error instanceof ApiError
      ? upload.error.detail
      : upload.error
      ? "Upload failed. Check the file format and try again."
      : null;

  const summaryData  = summary.data;
  const resultsData  = results.data;
  const resultRows = resultsData?.items ?? [];
  const uploadStatusSeed = upload.data && scanId === upload.data.scan_id
    ? {
        scan_id: upload.data.scan_id,
        status: upload.data.status,
        total_rows: upload.data.total_rows,
        processed_rows: 0,
        progress_percent: 0,
        valid_rows: 0,
        invalid_rows: 0,
        skipped_rows: 0,
        p0_count: 0,
        p1_count: 0,
        p2_count: 0,
        p3_count: 0,
        created_at: null,
        started_at: null,
        completed_at: null,
        cancelled_at: null,
        error_message: null,
      } satisfies RiskScanStatus
    : null;
  const progressData = statusData ?? uploadStatusSeed;

  // Tier counts for filter tab badges (from summary when available)
  const tierCounts: Record<string, number> = summaryData
    ? {
        P0: summaryData.tier_distribution.critical,
        P1: summaryData.tier_distribution.high,
        P2: summaryData.tier_distribution.medium,
        P3: summaryData.tier_distribution.low,
      }
    : {};

  return (
    <div className="mx-auto max-w-7xl space-y-4 pb-8">

      {/* ── Header ─────────────────────────────────────────────── */}
      <div
        className="pb-4"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}
      >
        <p className="route-label mb-1">Portfolio Intelligence</p>
        <h1 className="page-hero-title">Portfolio Risk Scan</h1>
        <p
          className="mt-1 text-[13px] leading-relaxed"
          style={{ color: "#4B5563", maxWidth: "600px" }}
        >
          Bulk transaction intelligence for batch fraud scoring, priority routing, and case promotion.
        </p>
      </div>

      {/* ── Upload panel ───────────────────────────────────────── */}
      <div className="card p-5">
        <p className="section-label mb-3">Upload CSV</p>
        <div className="flex flex-wrap items-start gap-4">
          {/* File picker */}
          <div className="min-w-0 flex-1 space-y-2">
            <label
              className="block w-full cursor-pointer rounded-md px-3 py-2.5 text-[13px]"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.10)",
                color: selectedFile ? "#C9D1D9" : "#6B7280",
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                className="sr-only"
              />
              {selectedFile ? selectedFile.name : "Choose a CSV file…"}
            </label>
            <p className="text-[11px]" style={{ color: "#6B7280" }}>
              Maximum 10,000 data rows. Required columns: transaction_id, amount,
              timestamp, country, payment_method.
            </p>
          </div>

          {/* Run button */}
          <button
            type="button"
            onClick={handleUpload}
            disabled={!selectedFile || upload.isPending}
            className="rounded-md px-5 py-2.5 text-[13px] font-semibold"
            style={{
              background:
                !selectedFile || upload.isPending
                  ? "rgba(34,211,238,0.04)"
                  : "rgba(34,211,238,0.10)",
              border: "1px solid rgba(34,211,238,0.22)",
              color:
                !selectedFile || upload.isPending ? "#4B5563" : "#22D3EE",
              cursor:
                !selectedFile || upload.isPending ? "not-allowed" : "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {upload.isPending ? "Scanning…" : "Run Risk Scan"}
          </button>
        </div>
      </div>

      {/* ── Upload error ────────────────────────────────────────── */}
      {uploadError && <ErrorBanner message={uploadError} />}

      {/* ── Guided empty state ──────────────────────────────────── */}
      {!scanId && !upload.isPending && (
        <div
          className="card flex flex-col items-center justify-center gap-2 py-14 text-center"
          style={{ background: "rgba(255,255,255,0.015)" }}
        >
          <p className="text-[14px] font-semibold" style={{ color: "#C9D1D9" }}>
            No scan active
          </p>
          <p
            className="max-w-sm text-[12px] leading-relaxed"
            style={{ color: "#6B7280" }}
          >
            Upload a CSV to score a batch of transactions, view risk tier distribution,
            exposure concentration, and promote high-priority cases.
          </p>
        </div>
      )}

      {/* ── Validation strip ────────────────────────────────────── */}
      {progressData && <ProgressCard status={progressData} />}
      {status.isError && (
        <ErrorBanner message="Could not load scan status. Check API connectivity." />
      )}

      {/* ── Summary loading skeleton ─────────────────────────────── */}
      {scanId && isComplete && summary.isLoading && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-20 animate-pulse rounded-lg"
              style={{ background: "rgba(255,255,255,0.04)" }}
            />
          ))}
        </div>
      )}

      {/* ── Summary error ──────────────────────────────────────── */}
      {isComplete && summary.isError && (
        <ErrorBanner message="Could not load scan summary. Check API connectivity." />
      )}

      {/* ── Portfolio KPI rail ─────────────────────────────────── */}
      {summaryData && <PortfolioKPIs summary={summaryData} />}

      {/* ── Distribution / Exposure / Patterns ─────────────────── */}
      {summaryData && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <TierDistribution summary={summaryData} />
          <ExposurePanel    summary={summaryData} />
          <RiskPatterns     summary={summaryData} />
        </div>
      )}

      {/* ── Results section ─────────────────────────────────────── */}
      {scanId && isComplete && (
        <section className="space-y-3">
          {/* Section header + tier filter tabs */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="section-label">
              Scan Results
              {resultsData && (
                <span
                  className="ml-2 font-normal normal-case tracking-normal"
                  style={{ color: "#6B7280" }}
                >
                  {resultsData.total_items} row{resultsData.total_items !== 1 ? "s" : ""}
                </span>
              )}
            </p>

            {/* Tier filter tabs */}
            <div className="flex flex-wrap gap-1.5">
              {TIER_TABS.map(({ label, value }) => {
                const active = tierFilter === value;
                const ps = value ? PRIORITY_STYLE[value] : null;
                return (
                  <button
                    key={label}
                    type="button"
                    onClick={() => {
                      setTierFilter(value);
                      setResultsPage(1);
                    }}
                    className="rounded px-2.5 py-1 text-[11px] font-semibold"
                    style={{
                      background: active
                        ? (ps?.bg ?? "rgba(34,211,238,0.10)")
                        : "rgba(255,255,255,0.04)",
                      border: `1px solid ${
                        active
                          ? (ps?.border ?? "rgba(34,211,238,0.28)")
                          : "rgba(255,255,255,0.08)"
                      }`,
                      color: active
                        ? (ps?.color ?? "#22D3EE")
                        : "#8B949E",
                    }}
                  >
                    {label}
                    {value !== undefined && tierCounts[value] !== undefined && (
                      <span
                        className="ml-1 font-normal"
                        style={{
                          color: active
                            ? (ps?.color ?? "#22D3EE")
                            : "#6B7280",
                        }}
                      >
                        {tierCounts[value]}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Promote error */}
          {promoteError && <ErrorBanner message={promoteError} />}

          {results.isLoading && <Skeleton rows={5} />}
          {results.isError && (
            <ErrorBanner message="Could not load scan results. Check API connectivity." />
          )}
          {resultsData && (
            <PaginationControls
              page={resultsData.page}
              totalPages={resultsData.total_pages}
              totalItems={resultsData.total_items}
              pageSize={resultsData.page_size}
              onPageChange={setResultsPage}
            />
          )}
          {resultsData && (
            <ResultsTable
              rows={resultRows}
              pendingId={pendingPromoteId}
              onPromote={handlePromote}
            />
          )}
        </section>
      )}

      {/* ── Export bar ──────────────────────────────────────────── */}
      {scanId && isComplete && !summary.isLoading && (
        <div
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg px-4 py-3"
          style={{
            background: "rgba(255,255,255,0.025)",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <p className="text-[12px]" style={{ color: "#8B949E" }}>
            Download all scan results including validation status and scoring outputs.
          </p>
          <button
            type="button"
            onClick={handleExport}
            disabled={!isComplete}
            className="rounded-md px-4 py-2 text-[12px] font-semibold"
            style={{
              background: "rgba(167,139,250,0.08)",
              border: "1px solid rgba(167,139,250,0.22)",
              color: "#A78BFA",
              cursor: isComplete ? "pointer" : "not-allowed",
            }}
          >
            Export CSV
          </button>
        </div>
      )}

      {/* ── Export error ────────────────────────────────────────── */}
      {exportError && <ErrorBanner message={exportError} />}
    </div>
  );
}
