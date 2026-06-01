"use client";

import { useEffect, useState } from "react";
import type { RiskScanSummary, RiskScanStatus, RecentScan } from "@/types/riskScan";

// ── Format helpers ───────────────────────────────────────────────────────────

function fmtCurrencyFull(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(n);
}

function fmtCompact(n: number | null): string {
  if (n === null) return "—";
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${Math.round(n / 1e3)}K`;
  return fmtCurrencyFull(n);
}

function fmtRuntime(
  startIso: string | null | undefined,
  endIso: string | null | undefined,
): string {
  if (!startIso || !endIso) return "—";
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
  if (ms < 0) return "—";
  const totalSec = Math.floor(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function pct(count: number, total: number): string {
  if (total === 0) return "0%";
  return `${((count / total) * 100).toFixed(1)}%`;
}

// ── Priority tokens ──────────────────────────────────────────────────────────

const P_STYLE: Record<string, { color: string; bg: string; border: string }> = {
  P0: { color: "#FF4D4D", bg: "rgba(255,77,77,0.10)",   border: "rgba(255,77,77,0.28)"  },
  P1: { color: "#F59E0B", bg: "rgba(245,158,11,0.10)",  border: "rgba(245,158,11,0.28)" },
  P2: { color: "#22D3EE", bg: "rgba(34,211,238,0.10)",  border: "rgba(34,211,238,0.28)" },
  P3: { color: "#8B949E", bg: "rgba(139,148,158,0.10)", border: "rgba(139,148,158,0.20)"},
};

// ── Markdown builder ─────────────────────────────────────────────────────────

function buildMarkdown(
  scanId: string,
  summary: RiskScanSummary,
  statusData: RiskScanStatus | null,
  recentMatch: RecentScan | null,
  generatedAt: string,
): string {
  const filename = summary.filename ?? recentMatch?.filename ?? "—";
  const createdAt  = summary.created_at  ?? recentMatch?.created_at  ?? null;
  const completedAt = summary.completed_at ?? recentMatch?.completed_at ?? null;
  const startedAt  = statusData?.started_at ?? recentMatch?.started_at ?? null;
  const runtime    = fmtRuntime(startedAt ?? createdAt, completedAt);
  const processed  = statusData?.processed_rows ?? recentMatch?.processed_rows ?? summary.total_rows;

  const p0 = summary.tier_distribution.critical;
  const p1 = summary.tier_distribution.high;
  const p2 = summary.tier_distribution.medium;
  const p3 = summary.tier_distribution.low;
  const total = summary.total_rows;

  const highestTier = p0 > 0 ? "P0" : p1 > 0 ? "P1" : p2 > 0 ? "P2" : p3 > 0 ? "P3" : null;
  const focus = highestTier ? FOCUS_COPY[highestTier] : "No scored rows present in this scan.";

  return [
    "# Portfolio Risk Scan Report",
    "",
    "## Report Header",
    "",
    "| Field | Value |",
    "|---|---|",
    `| **Report Title** | Portfolio Risk Scan Report |`,
    `| **Scan Filename** | \`${filename}\` |`,
    `| **Scan UUID** | \`${scanId}\` |`,
    `| **Status** | COMPLETE |`,
    `| **Generated** | ${generatedAt} |`,
    "",
    "## Processing Summary",
    "",
    "| Metric | Value |",
    "|---|---|",
    `| Total Rows | ${total.toLocaleString()} |`,
    `| Processed Rows | ${processed.toLocaleString()} |`,
    `| Valid Rows | ${summary.valid_rows.toLocaleString()} |`,
    `| Invalid Rows | ${summary.invalid_rows.toLocaleString()} |`,
    `| Skipped Rows | ${summary.skipped_rows.toLocaleString()} |`,
    `| Completion Time | ${runtime} |`,
    "",
    "## Risk Distribution",
    "",
    "| Priority | Count | Share |",
    "|---|---|---|",
    `| P0 Critical | ${p0.toLocaleString()} | ${pct(p0, total)} |`,
    `| P1 High     | ${p1.toLocaleString()} | ${pct(p1, total)} |`,
    `| P2 Medium   | ${p2.toLocaleString()} | ${pct(p2, total)} |`,
    `| P3 Low      | ${p3.toLocaleString()} | ${pct(p3, total)} |`,
    "",
    "## Exposure Summary",
    "",
    "| Metric | Amount |",
    "|---|---|",
    `| Total Exposure    | ${fmtCompact(summary.exposure.total_amount)} |`,
    `| Critical (P0)     | ${fmtCompact(summary.exposure.critical_amount)} |`,
    `| High (P1)         | ${fmtCompact(summary.exposure.high_amount)} |`,
    "",
    "## Operational Prioritisation",
    "",
    `**Highest priority tier:** ${highestTier ?? "None"}`,
    "",
    `**Analyst focus:** ${focus}`,
    "",
    "## Review Workflow",
    "",
    "- Result table: available",
    "- Filtered export: available",
    "- Promote to case: available",
    "- Scan resume (UUID): available",
    "",
    "## Validation Scope",
    "",
    "Report generated from the local synthetic benchmark scan record.",
    "Institution deployment would require security, governance, monitoring, and model validation controls.",
  ].join("\n");
}

const FOCUS_COPY: Record<string, string> = {
  P0: "Immediate action required. Review all P0 Critical transactions before any P1 work.",
  P1: "High-priority review queue. Prioritise P1 High transactions before broad P3 review.",
  P2: "No P0/P1 cases present. Process P2 Medium transactions per standard review cadence.",
  P3: "Low-risk portfolio. P3 Low transactions can be batched for routine review.",
};

// ── Props ────────────────────────────────────────────────────────────────────

interface ScanReportModalProps {
  scanId: string;
  summary: RiskScanSummary;
  statusData: RiskScanStatus | null;
  recentMatch: RecentScan | null;
  onClose: () => void;
}

// ── Component ────────────────────────────────────────────────────────────────

export function ScanReportModal({
  scanId,
  summary,
  statusData,
  recentMatch,
  onClose,
}: ScanReportModalProps) {
  const [copied, setCopied] = useState(false);
  const generatedAt = new Date().toLocaleString();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const filename   = summary.filename ?? recentMatch?.filename ?? "—";
  const createdAt  = summary.created_at  ?? recentMatch?.created_at  ?? null;
  const completedAt = summary.completed_at ?? recentMatch?.completed_at ?? null;
  const startedAt  = statusData?.started_at ?? recentMatch?.started_at ?? null;
  const runtime    = fmtRuntime(startedAt ?? createdAt, completedAt);
  const processed  = statusData?.processed_rows ?? recentMatch?.processed_rows ?? summary.total_rows;

  const p0 = summary.tier_distribution.critical;
  const p1 = summary.tier_distribution.high;
  const p2 = summary.tier_distribution.medium;
  const p3 = summary.tier_distribution.low;
  const total = summary.total_rows;

  const highestTier = p0 > 0 ? "P0" : p1 > 0 ? "P1" : p2 > 0 ? "P2" : p3 > 0 ? "P3" : null;
  const focusSuggestion = highestTier ? FOCUS_COPY[highestTier] : "No scored rows present.";

  function handleCopy() {
    const md = buildMarkdown(scanId, summary, statusData, recentMatch, generatedAt);
    navigator.clipboard.writeText(md).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  function handleDownload() {
    const md = buildMarkdown(scanId, summary, statusData, recentMatch, generatedAt);
    const blob = new Blob([md], { type: "text/markdown" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `risk-scan-report-${scanId.slice(0, 8)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const tiers = [
    { label: "P0 Critical", key: "P0" as const, count: p0 },
    { label: "P1 High",     key: "P1" as const, count: p1 },
    { label: "P2 Medium",   key: "P2" as const, count: p2 },
    { label: "P3 Low",      key: "P3" as const, count: p3 },
  ];

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0"
        style={{ background: "rgba(0,0,0,0.65)", zIndex: 50 }}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div
        className="fixed inset-0 flex items-center justify-center p-4"
        style={{ zIndex: 60 }}
        role="dialog"
        aria-modal="true"
        aria-label="Scan Report"
      >
        <div
          data-testid="scan-report-modal"
          className="flex w-full max-w-2xl flex-col rounded-xl"
          style={{
            background: "#0D1117",
            border: "1px solid rgba(255,255,255,0.10)",
            maxHeight: "90vh",
          }}
        >

          {/* ── Modal header ──────────────────────────────────── */}
          <div
            className="flex shrink-0 items-center justify-between px-5 py-4"
            style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}
          >
            <div>
              <p
                className="text-[10px] font-semibold uppercase tracking-widest"
                style={{ color: "#4B5563" }}
              >
                Portfolio Intelligence
              </p>
              <h2
                className="mt-0.5 text-[16px] font-semibold"
                style={{ color: "#C9D1D9" }}
              >
                Risk Scan Report
              </h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close report"
              className="rounded px-2.5 py-1 text-[13px]"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.08)",
                color: "#6B7280",
                cursor: "pointer",
              }}
            >
              ✕
            </button>
          </div>

          {/* ── Scrollable body ───────────────────────────────── */}
          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5">

            {/* 1 — Report Header */}
            <section aria-label="Report header">
              <p className="section-label mb-3">Report Header</p>
              <div
                className="overflow-hidden rounded-lg"
                style={{ border: "1px solid rgba(255,255,255,0.07)" }}
              >
                {(
                  [
                    { label: "Scan Filename", value: filename,   mono: true  },
                    { label: "Scan UUID",     value: scanId,     mono: true  },
                    { label: "Status",        value: "COMPLETE", accent: "#10B981" },
                    { label: "Generated",     value: generatedAt },
                  ] as Array<{ label: string; value: string; mono?: boolean; accent?: string }>
                ).map(({ label, value, mono, accent }, i, arr) => (
                  <div
                    key={label}
                    className="flex items-baseline justify-between gap-4 px-4 py-2.5"
                    style={{
                      borderBottom: i < arr.length - 1 ? "1px solid rgba(255,255,255,0.05)" : "none",
                      background: i % 2 === 0 ? "rgba(255,255,255,0.015)" : "transparent",
                    }}
                  >
                    <span className="shrink-0 text-[11px]" style={{ color: "#6B7280" }}>
                      {label}
                    </span>
                    <span
                      className={`break-all text-right text-[12px]${mono ? " font-mono" : ""}`}
                      style={{ color: accent ?? "#C9D1D9" }}
                    >
                      {value}
                    </span>
                  </div>
                ))}
              </div>
            </section>

            {/* 2 — Processing Summary */}
            <section aria-label="Processing summary">
              <p className="section-label mb-3">Processing Summary</p>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {[
                  { label: "Total Rows",      value: total.toLocaleString(),              color: "#C9D1D9" },
                  { label: "Processed",       value: processed.toLocaleString(),          color: "#C9D1D9" },
                  { label: "Valid",           value: summary.valid_rows.toLocaleString(), color: "#10B981" },
                  { label: "Invalid",         value: summary.invalid_rows.toLocaleString(),
                    color: summary.invalid_rows > 0 ? "#FF4D4D" : "#4B5563" },
                  { label: "Skipped",         value: summary.skipped_rows.toLocaleString(),
                    color: summary.skipped_rows > 0 ? "#F59E0B" : "#4B5563" },
                  { label: "Completion Time", value: runtime, color: "#8B949E" },
                ].map(({ label, value, color }) => (
                  <div
                    key={label}
                    className="rounded-lg px-3 py-2.5"
                    style={{
                      background: "rgba(255,255,255,0.03)",
                      border: "1px solid rgba(255,255,255,0.06)",
                    }}
                  >
                    <p
                      className="text-[20px] font-semibold tabular-nums leading-none"
                      style={{ color }}
                    >
                      {value}
                    </p>
                    <p className="mt-1 text-[10px]" style={{ color: "#4B5563" }}>
                      {label}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            {/* 3 — Risk Distribution */}
            <section aria-label="Risk distribution">
              <p className="section-label mb-3">Risk Distribution</p>
              <div
                className="overflow-hidden rounded-lg"
                style={{ border: "1px solid rgba(255,255,255,0.07)" }}
              >
                {/* Table head */}
                <div
                  className="grid grid-cols-4"
                  style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
                >
                  {["Priority", "Count", "Share", ""].map((h) => (
                    <div
                      key={h}
                      className="px-4 py-2 text-[10px] font-semibold uppercase tracking-wider"
                      style={{ color: "#4B5563" }}
                    >
                      {h}
                    </div>
                  ))}
                </div>

                {tiers.map(({ label, key, count }, i) => {
                  const ps      = P_STYLE[key];
                  const share   = pct(count, total);
                  const barPct  = total > 0
                    ? `${Math.max(count > 0 ? 2 : 0, (count / total) * 100).toFixed(1)}%`
                    : "0%";
                  return (
                    <div
                      key={key}
                      className="grid grid-cols-4 items-center"
                      style={{
                        borderBottom: i < tiers.length - 1
                          ? "1px solid rgba(255,255,255,0.04)"
                          : "none",
                      }}
                    >
                      <div className="px-4 py-2.5">
                        <span
                          className="rounded px-2 py-0.5 text-[11px] font-semibold"
                          style={{
                            color: ps.color,
                            background: ps.bg,
                            border: `1px solid ${ps.border}`,
                          }}
                        >
                          {label}
                        </span>
                      </div>
                      <div
                        className="px-4 py-2.5 tabular-nums text-[13px] font-semibold"
                        style={{ color: count > 0 ? ps.color : "#4B5563" }}
                      >
                        {count.toLocaleString()}
                      </div>
                      <div
                        className="px-4 py-2.5 tabular-nums text-[12px]"
                        style={{ color: "#8B949E" }}
                      >
                        {share}
                      </div>
                      <div className="px-4 py-2.5">
                        <div
                          className="h-1.5 w-full rounded-full"
                          style={{ background: "rgba(255,255,255,0.05)" }}
                        >
                          <div
                            className="h-1.5 rounded-full transition-all"
                            style={{
                              width: count > 0 ? barPct : "0%",
                              background: ps.color,
                              opacity: count > 0 ? 0.65 : 0,
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* 4 — Exposure Summary */}
            <section aria-label="Exposure summary">
              <p className="section-label mb-3">Exposure Summary</p>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: "Total Exposure", value: fmtCompact(summary.exposure.total_amount),    color: "#C9D1D9" },
                  { label: "Critical (P0)",  value: fmtCompact(summary.exposure.critical_amount), color: "#FF4D4D" },
                  { label: "High (P1)",      value: fmtCompact(summary.exposure.high_amount),     color: "#F59E0B" },
                ].map(({ label, value, color }) => (
                  <div
                    key={label}
                    className="rounded-lg px-3 py-3"
                    style={{
                      background: "rgba(255,255,255,0.03)",
                      border: "1px solid rgba(255,255,255,0.06)",
                    }}
                  >
                    <p
                      className="text-[18px] font-semibold tabular-nums leading-none"
                      style={{ color }}
                    >
                      {value}
                    </p>
                    <p className="mt-1.5 text-[10px]" style={{ color: "#4B5563" }}>
                      {label}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            {/* 5 — Operational Prioritisation */}
            <section aria-label="Operational prioritisation">
              <p className="section-label mb-3">Operational Prioritisation</p>
              <div
                className="space-y-3 rounded-lg p-4"
                style={{
                  background: "rgba(255,255,255,0.02)",
                  border: "1px solid rgba(255,255,255,0.07)",
                }}
              >
                <div className="flex items-center gap-3">
                  <span className="text-[11px]" style={{ color: "#6B7280" }}>
                    Highest priority tier
                  </span>
                  {highestTier ? (
                    <span
                      className="rounded px-2 py-0.5 text-[11px] font-bold"
                      style={{
                        color: P_STYLE[highestTier].color,
                        background: P_STYLE[highestTier].bg,
                        border: `1px solid ${P_STYLE[highestTier].border}`,
                      }}
                    >
                      {highestTier}
                    </span>
                  ) : (
                    <span className="text-[11px]" style={{ color: "#4B5563" }}>None</span>
                  )}
                </div>
                <p className="text-[12px] leading-relaxed" style={{ color: "#8B949E" }}>
                  {focusSuggestion}
                </p>
              </div>
            </section>

            {/* 6 — Review Workflow */}
            <section aria-label="Review workflow">
              <p className="section-label mb-3">Review Workflow</p>
              <div className="grid grid-cols-2 gap-2">
                {[
                  "Result table",
                  "Filtered export",
                  "Promote to case",
                  "Scan resume (UUID)",
                ].map((item) => (
                  <div
                    key={item}
                    className="flex items-center gap-2 rounded-lg px-3 py-2.5"
                    style={{
                      background: "rgba(16,185,129,0.05)",
                      border: "1px solid rgba(16,185,129,0.14)",
                    }}
                  >
                    <span style={{ color: "#10B981", fontSize: "12px" }}>✓</span>
                    <span className="text-[12px]" style={{ color: "#8B949E" }}>{item}</span>
                  </div>
                ))}
              </div>
            </section>

            {/* 7 — Validation Scope */}
            <section aria-label="Validation scope">
              <div
                className="rounded-lg px-4 py-3"
                style={{
                  background: "rgba(139,148,158,0.04)",
                  border: "1px solid rgba(139,148,158,0.14)",
                }}
              >
                <p
                  className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest"
                  style={{ color: "#4B5563" }}
                >
                  Validation Scope
                </p>
                <p className="text-[12px] leading-relaxed" style={{ color: "#6B7280" }}>
                  Report generated from the local synthetic benchmark scan record.
                  Institution deployment would require security, governance, monitoring,
                  and model validation controls.
                </p>
              </div>
            </section>

          </div>

          {/* ── Footer ────────────────────────────────────────── */}
          <div
            className="flex shrink-0 items-center justify-end gap-2 px-5 py-3"
            style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}
          >
            <button
              type="button"
              onClick={handleDownload}
              className="rounded px-3 py-1.5 text-[12px]"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.09)",
                color: "#6B7280",
                cursor: "pointer",
              }}
            >
              Download .md
            </button>
            <button
              type="button"
              onClick={handleCopy}
              className="rounded px-3 py-1.5 text-[12px] font-semibold"
              style={{
                background: copied ? "rgba(16,185,129,0.10)" : "rgba(34,211,238,0.08)",
                border: `1px solid ${copied ? "rgba(16,185,129,0.25)" : "rgba(34,211,238,0.22)"}`,
                color: copied ? "#10B981" : "#22D3EE",
                cursor: "pointer",
              }}
            >
              {copied ? "Copied" : "Copy Report Summary"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded px-3 py-1.5 text-[12px]"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.09)",
                color: "#6B7280",
                cursor: "pointer",
              }}
            >
              Close
            </button>
          </div>

        </div>
      </div>
    </>
  );
}
