"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getRecentRiskScans, getRiskScanExportUrl } from "@/lib/api/riskScan";
import {
  type RecentScan,
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
import { ScanResultDrawer } from "@/components/risk-scan/ScanResultDrawer";
import { ScanReportModal } from "@/components/risk-scan/ScanReportModal";

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
  if (n === null) return "N/A";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(n);
}

function fmtScore(n: number | null): string {
  if (n === null) return "N/A";
  return n.toFixed(3);
}

function fmtCompactCurrency(n: number | null): string {
  if (n === null) return "N/A";
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${Math.round(n / 1e3)}K`;
  return fmtCurrency(n);
}

function fmtTs(iso: string | null | undefined): string {
  if (!iso) return "N/A";
  return new Date(iso).toLocaleString();
}

/** Short relative timestamp for list views: "2h ago", "Jun 1, 3:22 PM", etc. */
function fmtShortTs(iso: string | null | undefined): string {
  if (!iso) return "N/A";
  const d   = new Date(iso);
  const now = new Date();
  const ms  = now.getTime() - d.getTime();
  if (ms < 0)         return d.toLocaleString();
  const mins  = Math.floor(ms / 60_000);
  if (mins < 1)       return "just now";
  if (mins < 60)      return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24)     return `${hours}h ago`;
  const days  = Math.floor(hours / 24);
  if (days < 7)       return `${days}d ago`;
  return d.toLocaleDateString("en-US", {
    month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}

/** Compact integer: 1,234,567 → "1.2M", 12345 → "12K" */
function fmtCompact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${Math.round(n / 1_000)}K`;
  return n.toLocaleString();
}

function fmtRuntime(
  startIso: string | null | undefined,
  endIso: string | null | undefined,
): string {
  if (!startIso || !endIso) return "N/A";
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
  if (ms < 0) return "N/A";
  const totalSec = Math.floor(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
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
  if (!reasons) return <span style={{ color: "#374151" }}>N/A</span>;
  const parts = reasons
    .split("|")
    .map((s) => s.trim())
    .filter(Boolean);
  if (parts.length === 0) return <span style={{ color: "#374151" }}>N/A</span>;
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
  onViewRow,
}: {
  rows: RiskScanResult[];
  pendingId: number | null;
  onPromote: (row: RiskScanResult) => void;
  onViewRow: (row: RiskScanResult) => void;
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
                  onClick={() => onViewRow(row)}
                  style={{
                    background: rowBg,
                    borderBottom: "1px solid rgba(255,255,255,0.04)",
                    cursor: "pointer",
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLTableRowElement).style.background =
                      "rgba(34,211,238,0.035)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLTableRowElement).style.background = rowBg;
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
                      <span style={{ color: "#374151" }}>N/A</span>
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
                      {row.transaction_id ?? "N/A"}
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
                    {row.country ?? "N/A"}
                  </td>

                  {/* Payment Method */}
                  <td style={{ padding: "8px 12px", color: "#8B949E", maxWidth: "120px" }}>
                    <span className="block truncate" title={row.payment_method ?? ""}>
                      {row.payment_method ?? "N/A"}
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
                      <span style={{ color: "#374151" }}>N/A</span>
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
                      <span style={{ color: "#374151" }}>N/A</span>
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

                  {/* Promotion — stopPropagation keeps row-click from firing */}
                  <td
                    style={{ padding: "8px 12px", whiteSpace: "nowrap" }}
                    onClick={(e) => e.stopPropagation()}
                  >
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
                      <span style={{ color: "#374151" }}>N/A</span>
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

const LAST_SCAN_ID_KEY = "fraud-console:last-risk-scan-id";
const LARGE_EXPORT_ROW_THRESHOLD = 100_000;

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

// ─── Scan detail header ──────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  COMPLETE:   "#10B981",
  PROCESSING: "#22D3EE",
  QUEUED:     "#F59E0B",
  FAILED:     "#FF4D4D",
  CANCELLED:  "#8B949E",
};
const STATUS_LABEL: Record<string, string> = {
  COMPLETE:   "Completed scan record",
  PROCESSING: "Processing",
  QUEUED:     "Queued",
  FAILED:     "Failed",
  CANCELLED:  "Cancelled",
};

function ScanDetailHeader({
  scanId,
  status,
  summary,
  recentMatch,
  isExportable,
  onExport,
  onReport,
}: {
  scanId: string;
  status: RiskScanStatus | null;
  summary: RiskScanSummary | null;
  recentMatch: RecentScan | null;
  isExportable: boolean;
  onExport: () => void;
  onReport?: () => void;
}) {
  const [copied, setCopied] = useState(false);

  function handleCopyId() {
    navigator.clipboard.writeText(scanId).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const st = status?.status ?? null;
  const statusColor = st ? (STATUS_COLOR[st] ?? "#8B949E") : "#8B949E";
  const statusLabel = st ? (STATUS_LABEL[st] ?? st) : "Loading…";

  const filename = summary?.filename ?? recentMatch?.filename ?? null;

  const createdAt  = status?.created_at  ?? summary?.created_at  ?? recentMatch?.created_at  ?? null;
  const startedAt  = status?.started_at  ?? recentMatch?.started_at  ?? null;
  const completedAt = status?.completed_at ?? summary?.completed_at ?? recentMatch?.completed_at ?? null;
  const runtime    = fmtRuntime(startedAt ?? createdAt, completedAt);

  const processedRows = status?.processed_rows ?? recentMatch?.processed_rows ?? 0;
  const totalRows     = status?.total_rows     ?? recentMatch?.total_rows     ?? 0;
  const validRows     = status?.valid_rows     ?? recentMatch?.valid_rows     ?? 0;
  const invalidRows   = status?.invalid_rows   ?? recentMatch?.invalid_rows   ?? 0;
  const p0 = status?.p0_count ?? recentMatch?.p0_count ?? 0;
  const p1 = status?.p1_count ?? recentMatch?.p1_count ?? 0;
  const p2 = status?.p2_count ?? recentMatch?.p2_count ?? 0;
  const p3 = status?.p3_count ?? recentMatch?.p3_count ?? 0;

  const totalExposure    = summary?.exposure.total_amount    ?? recentMatch?.total_amount    ?? null;
  const criticalExposure = summary?.exposure.critical_amount ?? recentMatch?.critical_amount ?? null;

  const metrics: Array<{ label: string; value: string; color?: string }> = [
    {
      label: "Processed",
      value: totalRows > 0
        ? `${processedRows.toLocaleString()} / ${totalRows.toLocaleString()}`
        : processedRows.toLocaleString(),
    },
    { label: "Valid",    value: validRows.toLocaleString(),   color: validRows > 0 ? "#10B981" : undefined },
    ...(invalidRows > 0 ? [{ label: "Invalid", value: invalidRows.toLocaleString(), color: "#FF4D4D" }] : []),
    ...(p0 > 0 ? [{ label: "P0 Critical", value: p0.toLocaleString(), color: "#FF4D4D" }] : []),
    ...(p1 > 0 ? [{ label: "P1 High",     value: p1.toLocaleString(), color: "#F59E0B" }] : []),
    ...(p2 > 0 ? [{ label: "P2 Medium",   value: p2.toLocaleString(), color: "#22D3EE" }] : []),
    ...(p3 > 0 ? [{ label: "P3 Low",      value: p3.toLocaleString(), color: "#8B949E" }] : []),
    ...(criticalExposure !== null && criticalExposure > 0
      ? [{ label: "Critical exposure", value: fmtCompactCurrency(criticalExposure), color: "#FF8080" }]
      : []),
    ...(totalExposure !== null && totalExposure > 0
      ? [{ label: "Total exposure", value: fmtCompactCurrency(totalExposure), color: "#C9D1D9" }]
      : []),
  ];

  return (
    <div className="card overflow-hidden">

      {/* ── Top row: status + filename + actions ── */}
      <div
        className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}
      >
        <div className="flex min-w-0 flex-wrap items-center gap-2.5">
          <span
            className="shrink-0 rounded px-2 py-0.5 font-mono text-[10px] font-bold"
            style={{
              color: statusColor,
              background: `${statusColor}14`,
              border: `1px solid ${statusColor}38`,
            }}
          >
            {statusLabel}
          </span>
          {filename && (
            <span
              className="truncate font-mono text-[13px] font-medium"
              style={{ color: "#C9D1D9", maxWidth: "400px" }}
              title={filename}
            >
              {filename}
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {isExportable && onReport && (
            <button
              type="button"
              onClick={onReport}
              className="rounded px-2.5 py-1 text-[11px] font-semibold"
              style={{
                background: "rgba(34,211,238,0.08)",
                border: "1px solid rgba(34,211,238,0.22)",
                color: "#22D3EE",
                cursor: "pointer",
              }}
            >
              View Scan Report
            </button>
          )}
          {isExportable && (
            <button
              type="button"
              onClick={onExport}
              className="rounded px-2.5 py-1 text-[11px] font-semibold"
              style={{
                background: "rgba(167,139,250,0.08)",
                border: "1px solid rgba(167,139,250,0.22)",
                color: "#A78BFA",
                cursor: "pointer",
              }}
            >
              Export CSV
            </button>
          )}
          <button
            type="button"
            onClick={handleCopyId}
            className="rounded px-2.5 py-1 text-[11px]"
            style={{
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.09)",
              color: copied ? "#10B981" : "#6B7280",
              cursor: "pointer",
            }}
          >
            {copied ? "Copied" : "Copy scan ID"}
          </button>
        </div>
      </div>

      {/* ── Metadata row: scan ID, timestamps, runtime ── */}
      <div
        className="flex flex-wrap items-center gap-x-6 gap-y-1.5 px-4 py-2.5"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
      >
        <span className="font-mono text-[11px]" style={{ color: "#4B5563" }} title={scanId}>
          <span style={{ color: "#6B7280" }}>ID </span>
          {scanId}
        </span>
        {createdAt && (
          <span className="text-[11px]" style={{ color: "#4B5563" }}>
            <span style={{ color: "#6B7280" }}>Created </span>
            {fmtTs(createdAt)}
          </span>
        )}
        {completedAt && (
          <span className="text-[11px]" style={{ color: "#4B5563" }}>
            <span style={{ color: "#6B7280" }}>Completed </span>
            {fmtTs(completedAt)}
          </span>
        )}
        {runtime !== "N/A" && (
          <span className="text-[11px]" style={{ color: "#4B5563" }}>
            <span style={{ color: "#6B7280" }}>Runtime </span>
            {runtime}
          </span>
        )}
      </div>

      {/* ── Metrics strip ── */}
      <div className="flex flex-wrap">
        {metrics.map((m, i) => (
          <div
            key={m.label}
            className="px-4 py-2.5"
            style={{
              borderRight: i < metrics.length - 1 ? "1px solid rgba(255,255,255,0.05)" : "none",
              borderBottom: "none",
            }}
          >
            <p
              className="font-mono text-[14px] font-semibold tabular-nums leading-none"
              style={{ color: m.color ?? "#C9D1D9" }}
            >
              {m.value}
            </p>
            <p className="mt-1 text-[10px] uppercase tracking-wider" style={{ color: "#4B5563" }}>
              {m.label}
            </p>
          </div>
        ))}
      </div>

      {/* ── Failed error message ── */}
      {st === "FAILED" && status?.error_message && (
        <div className="px-4 pb-3">
          <ErrorBanner message={status.error_message} />
        </div>
      )}
    </div>
  );
}

// ─── Recent scans panel ──────────────────────────────────────────────────────

const SCAN_STATUS_COLOR: Record<string, string> = {
  COMPLETE:   "#10B981",
  PROCESSING: "#22D3EE",
  FAILED:     "#FF4D4D",
  QUEUED:     "#F59E0B",
  CANCELLED:  "#8B949E",
};

const SCAN_STATUS_LABEL: Record<string, string> = {
  COMPLETE:   "Complete",
  PROCESSING: "Processing",
  QUEUED:     "Queued",
  FAILED:     "Failed",
  CANCELLED:  "Cancelled",
};

function RecentScansPanel({
  scans,
  activeScanId,
  onLoad,
}: {
  scans: RecentScan[];
  activeScanId: string | null;
  onLoad: (scanId: string) => void;
}) {
  if (scans.length === 0) {
    return (
      <div className="card p-5">
        <p className="section-label mb-2">Recent Portfolio Scans</p>
        <p className="text-[12px]" style={{ color: "#6B7280" }}>
          No scans found. Upload a CSV file to start your first portfolio risk scan.
        </p>
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      <div
        className="px-4 py-3"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}
      >
        <p className="section-label">Recent Portfolio Scans</p>
      </div>

      <div>
        {scans.map((scan, idx) => {
          const isActive     = scan.scan_id === activeScanId;
          const statusColor  = SCAN_STATUS_COLOR[scan.status]  ?? "#8B949E";
          const statusLabel  = SCAN_STATUS_LABEL[scan.status]  ?? scan.status;
          const displayTime  = scan.completed_at ?? scan.started_at ?? scan.created_at ?? null;

          // Row count: "10,000,000 / 10,000,000" when processing, "10,000,000" when done
          const rowCount =
            scan.status === "PROCESSING" && scan.total_rows > 0
              ? `${scan.processed_rows.toLocaleString()} / ${scan.total_rows.toLocaleString()}`
              : scan.total_rows > 0
              ? scan.total_rows.toLocaleString()
              : null;

          // Priority summary: show P0/P1 if non-zero, compact
          const priorityHints: Array<{ label: string; color: string }> = [];
          if (scan.p0_count > 0)
            priorityHints.push({ label: `P0 ${fmtCompact(scan.p0_count)}`, color: "#FF4D4D" });
          if (scan.p1_count > 0)
            priorityHints.push({ label: `P1 ${fmtCompact(scan.p1_count)}`, color: "#F59E0B" });

          return (
            <div
              key={scan.scan_id}
              onClick={() => { if (!isActive) onLoad(scan.scan_id); }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                padding: "10px 16px",
                borderBottom: idx < scans.length - 1 ? "1px solid rgba(255,255,255,0.05)" : "none",
                // Active: cyan left accent + tint; inactive: clickable hover
                borderLeft: isActive
                  ? "2px solid #22D3EE"
                  : "2px solid transparent",
                background: isActive ? "rgba(34,211,238,0.045)" : "transparent",
                cursor: isActive ? "default" : "pointer",
                transition: "background 0.1s",
              }}
              onMouseEnter={(e) => {
                if (!isActive)
                  (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.022)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.background = isActive
                  ? "rgba(34,211,238,0.045)"
                  : "transparent";
              }}
            >
              {/* Status dot */}
              <div
                style={{
                  flexShrink: 0,
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  background: statusColor,
                  boxShadow: isActive ? `0 0 6px ${statusColor}88` : "none",
                }}
              />

              {/* Main content */}
              <div style={{ minWidth: 0, flex: 1 }}>
                {/* Row 1: filename + status badge */}
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "3px" }}>
                  <span
                    className="font-mono text-[12px] font-medium"
                    style={{
                      color: "#C9D1D9",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      maxWidth: "280px",
                    }}
                    title={scan.filename ?? scan.scan_id}
                  >
                    {scan.filename ?? "N/A"}
                  </span>
                  <span
                    className="font-mono text-[9px] font-bold uppercase"
                    style={{
                      flexShrink: 0,
                      borderRadius: "3px",
                      padding: "2px 6px",
                      color: statusColor,
                      background: `${statusColor}14`,
                      border: `1px solid ${statusColor}30`,
                    }}
                  >
                    {statusLabel}
                  </span>
                </div>

                {/* Row 2: row count · priority hints · error · timestamp */}
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "0 10px" }}>
                  {rowCount && (
                    <span
                      className="font-mono text-[11px] tabular-nums"
                      style={{ color: "#6B7280" }}
                    >
                      {rowCount} rows
                    </span>
                  )}
                  {priorityHints.map((h) => (
                    <span
                      key={h.label}
                      className="text-[11px] tabular-nums"
                      style={{ color: h.color }}
                    >
                      {h.label}
                    </span>
                  ))}
                  {scan.status === "FAILED" && scan.error_message && (
                    <span
                      className="text-[11px]"
                      style={{
                        color: "#FF8080",
                        maxWidth: "200px",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                      title={scan.error_message}
                    >
                      {scan.error_message}
                    </span>
                  )}
                  {displayTime && (
                    <span className="text-[11px]" style={{ color: "#4B5563" }}>
                      {fmtShortTs(displayTime)}
                    </span>
                  )}
                </div>
              </div>

              {/* Open / Active button */}
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  if (!isActive) onLoad(scan.scan_id);
                }}
                disabled={isActive}
                className="text-[11px] font-semibold"
                style={{
                  flexShrink: 0,
                  borderRadius: "5px",
                  padding: "4px 10px",
                  background: isActive
                    ? "transparent"
                    : "rgba(34,211,238,0.08)",
                  border: isActive
                    ? "1px solid rgba(255,255,255,0.06)"
                    : "1px solid rgba(34,211,238,0.22)",
                  color: isActive ? "#374151" : "#22D3EE",
                  cursor: isActive ? "default" : "pointer",
                  minWidth: "48px",
                }}
              >
                {isActive ? "Active" : "Open"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Sample CSV ──────────────────────────────────────────────────────────────

function downloadSampleCSV() {
  const rows: string[][] = [
    ["transaction_id", "amount", "timestamp", "country", "payment_method"],
    // High-risk rows (5) — expected P0/BLOCK
    ["txn-p0-001", "9500",  "2026-06-28T02:15:00Z", "NG", "credit_card"],
    ["txn-p0-002", "8750",  "2026-06-27T03:45:00Z", "NG", "wire"],
    ["txn-p0-003", "12000", "2026-06-26T01:30:00Z", "RU", "credit_card"],
    ["txn-p0-004", "7800",  "2026-06-25T02:00:00Z", "IR", "credit_card"],
    ["txn-p0-005", "9200",  "2026-06-24T04:10:00Z", "NG", "wire"],
    // Medium-risk rows (5) — expected P1/REVIEW
    ["txn-p1-001", "2500",  "2026-06-28T22:30:00Z", "US", "credit_card"],
    ["txn-p1-002", "3200",  "2026-06-27T21:00:00Z", "GB", "credit_card"],
    ["txn-p1-003", "1800",  "2026-06-26T23:15:00Z", "CA", "digital_wallet"],
    ["txn-p1-004", "4100",  "2026-06-25T20:45:00Z", "AU", "credit_card"],
    ["txn-p1-005", "2900",  "2026-06-24T22:00:00Z", "DE", "bank_transfer"],
    // Low-risk rows (15) — expected P3/APPROVE
    ["txn-p3-001", "42.50",  "2026-06-28T13:30:00Z", "US", "debit_card"],
    ["txn-p3-002", "85.00",  "2026-06-27T10:15:00Z", "GB", "debit_card"],
    ["txn-p3-003", "28.75",  "2026-06-26T14:00:00Z", "US", "debit_card"],
    ["txn-p3-004", "65.00",  "2026-06-25T09:30:00Z", "CA", "debit_card"],
    ["txn-p3-005", "120.00", "2026-06-24T11:45:00Z", "AU", "digital_wallet"],
    ["txn-p3-006", "33.50",  "2026-06-23T13:00:00Z", "US", "debit_card"],
    ["txn-p3-007", "95.00",  "2026-06-22T15:30:00Z", "GB", "debit_card"],
    ["txn-p3-008", "48.25",  "2026-06-21T10:00:00Z", "US", "debit_card"],
    ["txn-p3-009", "72.00",  "2026-06-20T14:45:00Z", "CA", "digital_wallet"],
    ["txn-p3-010", "55.00",  "2026-06-19T12:15:00Z", "US", "debit_card"],
    ["txn-p3-011", "39.99",  "2026-06-18T09:00:00Z", "GB", "debit_card"],
    ["txn-p3-012", "88.50",  "2026-06-17T11:30:00Z", "AU", "debit_card"],
    ["txn-p3-013", "15.75",  "2026-06-16T13:45:00Z", "US", "debit_card"],
    ["txn-p3-014", "62.00",  "2026-06-15T10:30:00Z", "CA", "debit_card"],
    ["txn-p3-015", "44.00",  "2026-06-14T14:00:00Z", "US", "debit_card"],
  ];

  const csv = rows.map((row) => row.join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "fraud-console-sample-portfolio.csv";
  a.click();
  URL.revokeObjectURL(url);
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function RiskScanPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile]       = useState<File | null>(null);
  const [scanId, setScanId]                   = useState<string | null>(null);
  const [resumeInput, setResumeInput]         = useState("");
  const [resumeError, setResumeError]         = useState<string | null>(null);
  const [restoredScanId, setRestoredScanId]   = useState<string | null>(null);
  const [tierFilter, setTierFilter]           = useState<TierFilter>(undefined);
  const [resultsPage, setResultsPage]         = useState(1);
  const [pendingPromoteId, setPendingPromoteId] = useState<number | null>(null);
  const [promoteError, setPromoteError]       = useState<string | null>(null);
  const [exportError, setExportError]         = useState<string | null>(null);
  const [selectedResultRow, setSelectedResultRow] = useState<RiskScanResult | null>(null);
  const [showReport, setShowReport] = useState(false);

  // Recent scans panel
  const [recentScans, setRecentScans]             = useState<RecentScan[]>([]);
  const [recentScansLoading, setRecentScansLoading] = useState(true);
  const [recentScansError, setRecentScansError]   = useState<string | null>(null);

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

  function activateScan(nextScanId: string, source: "upload" | "manual" | "query" | "storage") {
    const trimmed = nextScanId.trim();
    if (!trimmed) return false;

    setScanId(trimmed);
    setResumeInput(trimmed);
    setTierFilter(undefined);
    setResultsPage(1);
    setPromoteError(null);
    setExportError(null);
    setResumeError(null);
    setRestoredScanId(source === "storage" ? trimmed : null);

    try {
      window.localStorage.setItem(LAST_SCAN_ID_KEY, trimmed);
    } catch {
      // localStorage may be unavailable in private or locked-down contexts.
    }

    return true;
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const queryScanId = params.get("scan_id")?.trim();

    let timerId: ReturnType<typeof setTimeout> | undefined;

    if (queryScanId) {
      timerId = setTimeout(() => activateScan(queryScanId, "query"), 0);
    } else {
      try {
        const savedScanId = window.localStorage.getItem(LAST_SCAN_ID_KEY)?.trim();
        if (savedScanId) {
          timerId = setTimeout(() => activateScan(savedScanId, "storage"), 0);
        }
      } catch {
        // Ignore storage failures; manual resume still works.
      }
    }

    return () => { if (timerId !== undefined) clearTimeout(timerId); };
  }, []);

  // Fetch recent scans once on mount
  useEffect(() => {
    let cancelled = false;
    getRecentRiskScans(10)
      .then((data) => {
        if (!cancelled) {
          setRecentScans(data);
          setRecentScansLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setRecentScansError("Could not load recent scans.");
          setRecentScansLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setSelectedFile(e.target.files?.[0] ?? null);
  }

  async function handleUpload() {
    if (!selectedFile) return;
    setPromoteError(null);
    setExportError(null);
    try {
      const r = await upload.mutateAsync(selectedFile);
      activateScan(r.scan_id, "upload");
    } catch {
      // error surfaced via upload.error below
    }
  }

  function handleResumeSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = resumeInput.trim();
    if (!trimmed) {
      setResumeError("Enter a public scan UUID to resume a completed scan.");
      return;
    }
    activateScan(trimmed, "manual");
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

  async function handleExport(tier?: string) {
    if (!scanId || !isComplete) return;
    setExportError(null);

    // Row count: use the tier-specific count when filtering, otherwise total.
    const tierCounts: Record<string, number> = summaryData
      ? {
          P0: summaryData.tier_distribution.critical,
          P1: summaryData.tier_distribution.high,
          P2: summaryData.tier_distribution.medium,
          P3: summaryData.tier_distribution.low,
        }
      : {};
    const rowCount = tier && tierCounts[tier] !== undefined
      ? tierCounts[tier]
      : (summaryData?.total_rows ?? statusData?.total_rows ?? 0);

    if (rowCount >= LARGE_EXPORT_ROW_THRESHOLD) {
      const tierLabel = tier ? ` (${tier} tier)` : "";
      const confirmed = window.confirm(
        `This export${tierLabel} contains ${rowCount.toLocaleString()} rows and may be a very large CSV. Continue with the download?`,
      );
      if (!confirmed) return;
    }

    window.location.assign(getRiskScanExportUrl(scanId, tier));
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
              Large scans are processed asynchronously. Row limits depend on
              backend configuration. Required columns: transaction_id, amount,
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

        {/* Sample CSV helper */}
        <div
          className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-md px-3 py-3"
          style={{
            background: "rgba(255,255,255,0.02)",
            border: "1px solid rgba(255,255,255,0.07)",
          }}
        >
          <p className="text-[12px]" style={{ color: "#6B7280" }}>
            Use a small sample portfolio to test the hosted risk scan workflow.
          </p>
          <button
            type="button"
            onClick={downloadSampleCSV}
            className="shrink-0 rounded-md px-3 py-1.5 text-[12px] font-semibold"
            style={{
              background: "rgba(167,139,250,0.08)",
              border: "1px solid rgba(167,139,250,0.22)",
              color: "#A78BFA",
              cursor: "pointer",
            }}
          >
            Download Sample CSV
          </button>
        </div>
      </div>

      {/* Resume existing scan */}
      <form className="card p-5" onSubmit={handleResumeSubmit}>
        <div className="flex flex-wrap items-end gap-4">
          <div className="min-w-0 flex-1 space-y-2">
            <p className="section-label">Resume Existing Scan</p>
            <input
              type="text"
              value={resumeInput}
              onChange={(e) => {
                setResumeInput(e.target.value);
                setResumeError(null);
              }}
              placeholder="Paste public scan UUID"
              className="block w-full rounded-md px-3 py-2.5 font-mono text-[13px] outline-none"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.10)",
                color: "#C9D1D9",
              }}
            />
            <p className="text-[11px]" style={{ color: "#6B7280" }}>
              Use the public scan_id UUID from a previous async scan. Results
              remain paginated at 100 rows per page.
            </p>
          </div>
          <button
            type="submit"
            className="rounded-md px-5 py-2.5 text-[13px] font-semibold"
            style={{
              background: "rgba(34,211,238,0.10)",
              border: "1px solid rgba(34,211,238,0.22)",
              color: "#22D3EE",
              whiteSpace: "nowrap",
            }}
          >
            Load Scan
          </button>
        </div>
        {resumeError && (
          <div className="mt-3">
            <ErrorBanner message={resumeError} />
          </div>
        )}
        {restoredScanId && scanId === restoredScanId && (
          <p className="mt-3 text-[12px]" style={{ color: "#8B949E" }}>
            Restored last scan from this browser:{" "}
            <span className="font-mono" style={{ color: "#C9D1D9" }}>
              {restoredScanId}
            </span>
          </p>
        )}
      </form>

      {/* ── Upload error ────────────────────────────────────────── */}
      {uploadError && <ErrorBanner message={uploadError} />}

      {/* ── Recent Portfolio Scans ──────────────────────────────── */}
      {recentScansLoading ? (
        <div className="card p-5">
          <p className="section-label mb-3">Recent Portfolio Scans</p>
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="h-12 animate-pulse rounded"
                style={{ background: "rgba(255,255,255,0.04)" }}
              />
            ))}
          </div>
        </div>
      ) : recentScansError ? (
        <div className="card p-5">
          <p className="section-label mb-2">Recent Portfolio Scans</p>
          <ErrorBanner message={recentScansError} />
        </div>
      ) : (
        <RecentScansPanel
          scans={recentScans}
          activeScanId={scanId}
          onLoad={(id) => activateScan(id, "manual")}
        />
      )}

      {/* ── Scan Detail Header ─────────────────────────────────── */}
      {scanId && (
        <ScanDetailHeader
          scanId={scanId}
          status={statusData ?? null}
          summary={summaryData ?? null}
          recentMatch={recentScans.find((s) => s.scan_id === scanId) ?? null}
          isExportable={isComplete}
          onExport={handleExport}
          onReport={isComplete && summaryData ? () => setShowReport(true) : undefined}
        />
      )}

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
              onViewRow={setSelectedResultRow}
            />
          )}
        </section>
      )}

      {/* ── Export section ──────────────────────────────────────── */}
      {scanId && isComplete && !summary.isLoading && (() => {
        const filteredCount = tierFilter && summaryData
          ? ({
              P0: summaryData.tier_distribution.critical,
              P1: summaryData.tier_distribution.high,
              P2: summaryData.tier_distribution.medium,
              P3: summaryData.tier_distribution.low,
            }[tierFilter] ?? 0)
          : null;
        const totalCount = summaryData?.total_rows ?? statusData?.total_rows ?? 0;

        return (
          <div className="card p-4" aria-label="Export scan results">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-1">
                <p className="section-label">Export Scan Results</p>
                <p
                  className="text-[11px]"
                  style={{ color: "#6B7280", maxWidth: "380px" }}
                >
                  {tierFilter
                    ? `Current filter: ${tierFilter}. Export the filtered view or all results.`
                    : "Results are streamed from the server. Large scans may take time to complete."}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {/* Filtered export button — visible when a tier is selected */}
                {tierFilter && filteredCount !== null && (
                  <button
                    type="button"
                    onClick={() => handleExport(tierFilter)}
                    className="rounded-md px-4 py-2 text-[12px] font-semibold"
                    style={{
                      background: "rgba(167,139,250,0.10)",
                      border: "1px solid rgba(167,139,250,0.30)",
                      color: "#A78BFA",
                      cursor: "pointer",
                    }}
                  >
                    Export {tierFilter} Only
                    {filteredCount > 0 && (
                      <span
                        className="ml-1.5 font-normal"
                        style={{ color: "#8B7FBF" }}
                      >
                        {fmtCompact(filteredCount)}
                      </span>
                    )}
                  </button>
                )}

                {/* Full export — always available */}
                <button
                  type="button"
                  onClick={() => handleExport()}
                  className="rounded-md px-4 py-2 text-[12px] font-semibold"
                  style={{
                    background: tierFilter
                      ? "rgba(255,255,255,0.04)"
                      : "rgba(167,139,250,0.08)",
                    border: tierFilter
                      ? "1px solid rgba(255,255,255,0.09)"
                      : "1px solid rgba(167,139,250,0.22)",
                    color: tierFilter ? "#6B7280" : "#A78BFA",
                    cursor: "pointer",
                  }}
                >
                  Export All Results
                  {totalCount > 0 && (
                    <span
                      className="ml-1.5 font-normal"
                      style={{ color: tierFilter ? "#4B5563" : "#8B7FBF" }}
                    >
                      {fmtCompact(totalCount)}
                    </span>
                  )}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* ── Export error ────────────────────────────────────────── */}
      {exportError && <ErrorBanner message={exportError} />}

      {/* ── Result detail drawer ─────────────────────────────────── */}
      {selectedResultRow && (
        <ScanResultDrawer
          row={selectedResultRow}
          scanId={scanId}
          filename={summaryData?.filename ?? recentScans.find((s) => s.scan_id === scanId)?.filename ?? null}
          onClose={() => setSelectedResultRow(null)}
          onPromote={async (row) => {
            await handlePromote(row);
            setSelectedResultRow(null);
          }}
          isPromoting={pendingPromoteId === selectedResultRow.id}
        />
      )}

      {/* ── Scan report modal ────────────────────────────────────── */}
      {showReport && summaryData && scanId && (
        <ScanReportModal
          scanId={scanId}
          summary={summaryData}
          statusData={statusData ?? null}
          recentMatch={recentScans.find((s) => s.scan_id === scanId) ?? null}
          onClose={() => setShowReport(false)}
        />
      )}
    </div>
  );
}
