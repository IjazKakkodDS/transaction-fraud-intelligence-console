"use client";

import { useEffect } from "react";
import Link from "next/link";
import type { RiskScanResult } from "@/types/riskScan";

// ── Design tokens ────────────────────────────────────────────────────────────

const PRIORITY_STYLE: Record<string, { color: string; bg: string; border: string }> = {
  P0: { color: "#FF4D4D", bg: "rgba(255,77,77,0.10)",   border: "rgba(255,77,77,0.28)"  },
  P1: { color: "#F59E0B", bg: "rgba(245,158,11,0.10)",  border: "rgba(245,158,11,0.28)" },
  P2: { color: "#22D3EE", bg: "rgba(34,211,238,0.10)",  border: "rgba(34,211,238,0.28)" },
  P3: { color: "#8B949E", bg: "rgba(139,148,158,0.10)", border: "rgba(139,148,158,0.20)"},
};

const DECISION_COLOR: Record<string, string> = {
  BLOCK:   "#FF4D4D",
  REVIEW:  "#F59E0B",
  APPROVE: "#10B981",
};

// ── Rich scenario classification (Phase 12F-4) ───────────────────────────────
//
// Scenario family labels are appended by the backend as the final reason code
// when the row comes from a rich synthetic CSV. Detecting them here lets the
// drawer surface a clean "Scenario" section without any backend payload change.
//
// Rich signal codes are the 8 new codes added in Phase 12F-3. They get amber
// styling to distinguish them from the 7 legacy red reason codes.

const SCENARIO_LABEL_MAP: Record<string, string> = {
  "Account takeover pattern detected":      "Account Takeover",
  "Card testing velocity pattern":          "Card Testing",
  "High-velocity spend pattern":            "High-Velocity Spend",
  "Unusual geographic pattern":             "Unusual Geography",
  "New payee transfer risk":                "New Payee Transfer",
  "Merchant risk spike":                    "Merchant Risk Spike",
  "Mule account behaviour pattern":         "Mule Account",
  "Refund and chargeback abuse pattern":    "Refund / Chargeback Abuse",
  "Dormant account reactivation detected":  "Dormant Account Reactivation",
  "Cross-border high-value transaction":    "Cross-Border High-Value",
  "Device mismatch detected":               "Device Mismatch",
  "Suspicious repeated attempts detected":  "Suspicious Repeated Attempts",
};

const RICH_SIGNAL_SET = new Set([
  "Unrecognised device with low trust score",
  "Geographic location inconsistent with registered address",
  "Transaction velocity exceeds 1-hour baseline",
  "Multiple failed attempts preceding this transaction",
  "High-risk merchant",
  "First-time payment to unknown payee",
  "High chargeback history",
  "Transaction amount significantly above 30-day average",
]);

// ── Format helpers ───────────────────────────────────────────────────────────

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

function fmtTs(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

// Normalise device_id values that pandas serialises as "NaN" or "None" for
// empty-string CSV cells. Treat them the same as null/absent.
function normalizeDeviceId(id: string | null | undefined): string | null {
  if (!id) return null;
  const lower = id.toLowerCase().trim();
  if (lower === "nan" || lower === "none" || lower === "") return null;
  return id;
}

// ── Small layout primitives ──────────────────────────────────────────────────

function SectionHead({ label }: { label: string }) {
  return (
    <p
      className="px-5 pb-2 pt-1 text-[10px] font-semibold uppercase tracking-widest"
      style={{ color: "#4B5563" }}
    >
      {label}
    </p>
  );
}

function FieldRow({
  label,
  value,
  mono = false,
  valueColor = "#C9D1D9",
}: {
  label: string;
  value: string;
  mono?: boolean;
  valueColor?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 px-5 py-1.5">
      <span className="shrink-0 text-[11px]" style={{ color: "#6B7280" }}>
        {label}
      </span>
      <span
        className={`max-w-[220px] break-all text-right text-[12px] ${mono ? "font-mono" : ""}`}
        style={{ color: valueColor }}
      >
        {value}
      </span>
    </div>
  );
}

// ── Drawer ───────────────────────────────────────────────────────────────────

export interface ScanResultDrawerProps {
  row: RiskScanResult;
  scanId: string | null;
  filename: string | null;
  onClose: () => void;
  onPromote: (row: RiskScanResult) => void;
  isPromoting: boolean;
}

export function ScanResultDrawer({
  row,
  scanId,
  filename,
  onClose,
  onPromote,
  isPromoting,
}: ScanResultDrawerProps) {
  const ps          = row.operational_priority ? PRIORITY_STYLE[row.operational_priority] : null;
  const decColor    = row.decision ? (DECISION_COLOR[row.decision] ?? "#6B7280") : "#6B7280";
  const scoreColor  =
    row.risk_score === null ? "#6B7280"
    : row.risk_score >= 0.8 ? "#FF4D4D"
    : row.risk_score >= 0.6 ? "#F59E0B"
    : "#10B981";

  const allReasons = row.reasons
    ? row.reasons.split("|").map((r) => r.trim()).filter(Boolean)
    : [];

  // Classify reasons into three groups.
  // scenarioLabel  — last entry matching a known scenario family label
  // richSignals    — entries matching Phase 12F-3 rich signal codes
  // legacyReasons  — everything else (the original 7 legacy codes)
  // Legacy scans produce no rich signals and no scenario label; those groups
  // remain empty and their UI sections are not rendered.
  const scenarioLabel   = allReasons.find((r) => r in SCENARIO_LABEL_MAP) ?? null;
  const richSignals     = allReasons.filter((r) => RICH_SIGNAL_SET.has(r));
  const legacyReasons   = allReasons.filter(
    (r) => !RICH_SIGNAL_SET.has(r) && !(r in SCENARIO_LABEL_MAP)
  );
  const hasAnyReasons   = allReasons.length > 0;

  const deviceId = normalizeDeviceId(row.device_id);

  const hasAttributes =
    !!row.timestamp ||
    !!row.country ||
    !!row.payment_method ||
    !!row.merchant_category ||
    !!deviceId;

  const hasModelContext =
    row.model_prediction !== null || row.rule_flag !== null;

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  function handleCopyTxId() {
    if (row.transaction_id) {
      navigator.clipboard.writeText(row.transaction_id).catch(() => {});
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        aria-hidden="true"
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.52)",
          zIndex: 40,
        }}
      />

      {/* Panel */}
      <aside
        role="complementary"
        aria-label="Transaction result detail"
        data-testid="result-detail-drawer"
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          height: "100vh",
          width: "min(420px, 100vw)",
          background: "#0D1117",
          borderLeft: "1px solid rgba(255,255,255,0.10)",
          zIndex: 50,
          display: "flex",
          flexDirection: "column",
          overflowY: "hidden",
          boxShadow: "-8px 0 40px rgba(0,0,0,0.45)",
        }}
      >
        {/* ── Header ── */}
        <div
          className="flex shrink-0 items-center justify-between gap-3 px-5 py-4"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}
        >
          <div className="flex min-w-0 items-center gap-2.5">
            {ps && (
              <span
                className="shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] font-bold"
                style={{ color: ps.color, background: ps.bg, border: `1px solid ${ps.border}` }}
              >
                {row.operational_priority}
              </span>
            )}
            <span
              className="truncate font-mono text-[12px] font-medium"
              style={{ color: "#C9D1D9", maxWidth: "270px" }}
              title={row.transaction_id ?? undefined}
            >
              {row.transaction_id ?? `Row ${row.row_number}`}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="shrink-0 rounded p-1.5"
            style={{
              background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.08)",
              color: "#6B7280",
              cursor: "pointer",
              fontSize: "16px",
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>

        {/* ── Scrollable body ── */}
        <div className="min-h-0 flex-1 overflow-y-auto">

          {/* ─ Risk Summary ─ */}
          <div className="pt-5">
            <SectionHead label="Risk Summary" />

            {/* Score hero */}
            <div
              className="mx-5 mb-3 flex items-start justify-between rounded-lg px-4 py-3"
              style={{
                background: "rgba(255,255,255,0.025)",
                border: "1px solid rgba(255,255,255,0.07)",
              }}
            >
              <div>
                <p className="text-[10px] uppercase tracking-widest" style={{ color: "#4B5563" }}>
                  Risk Score
                </p>
                <p
                  className="mt-0.5 font-mono text-[30px] font-semibold tabular-nums leading-none"
                  style={{ color: scoreColor }}
                >
                  {fmtScore(row.risk_score)}
                </p>
              </div>
              <div className="flex flex-col items-end gap-1.5 pt-0.5">
                {row.decision && (
                  <span
                    className="rounded px-2 py-0.5 font-mono text-[10px] font-bold"
                    style={{
                      color: decColor,
                      background: `${decColor}14`,
                      border: `1px solid ${decColor}38`,
                    }}
                  >
                    {row.decision}
                  </span>
                )}
                {ps && (
                  <span
                    className="rounded px-2 py-0.5 font-mono text-[10px] font-bold"
                    style={{ color: ps.color, background: ps.bg, border: `1px solid ${ps.border}` }}
                  >
                    {row.operational_priority}
                  </span>
                )}
                {row.validation_status && (
                  <span
                    className="rounded px-2 py-0.5 font-mono text-[9px] font-semibold uppercase"
                    style={{ color: "#6B7280", background: "rgba(255,255,255,0.04)" }}
                  >
                    {row.validation_status}
                  </span>
                )}
              </div>
            </div>

            {row.amount !== null && (
              <FieldRow label="Amount" value={fmtCurrency(row.amount)} mono />
            )}
            <FieldRow label="Row" value={String(row.row_number)} mono />
          </div>

          {/* ─ Scenario (rich records only) ─ */}
          {scenarioLabel && (
            <div className="pt-5">
              <SectionHead label="Scenario" />
              <div
                className="mx-5 mb-1 flex items-center gap-2.5 rounded-md px-3 py-2.5"
                style={{
                  background: "rgba(34,211,238,0.06)",
                  border: "1px solid rgba(34,211,238,0.18)",
                }}
              >
                <span
                  className="text-[10px] font-semibold uppercase tracking-widest shrink-0"
                  style={{ color: "#4B5563" }}
                >
                  Pattern
                </span>
                <span className="text-[12px] font-semibold" style={{ color: "#22D3EE" }}>
                  {SCENARIO_LABEL_MAP[scenarioLabel]}
                </span>
              </div>
            </div>
          )}

          {/* ─ Risk Signals ─ */}
          {hasAnyReasons && (
            <div className="pt-5">
              <SectionHead label="Risk Signals" />
              <div className="flex flex-wrap gap-1.5 px-5 pb-1">
                {/* Legacy signals — red chips (unchanged) */}
                {legacyReasons.map((r) => (
                  <span
                    key={r}
                    className="rounded px-2 py-1 text-[11px] font-medium leading-none"
                    style={{
                      background: "rgba(255,77,77,0.08)",
                      border: "1px solid rgba(255,77,77,0.16)",
                      color: "#FF8080",
                    }}
                  >
                    {r}
                  </span>
                ))}
                {/* Rich signal codes — amber chips */}
                {richSignals.map((r) => (
                  <span
                    key={r}
                    className="rounded px-2 py-1 text-[11px] font-medium leading-none"
                    style={{
                      background: "rgba(245,158,11,0.08)",
                      border: "1px solid rgba(245,158,11,0.20)",
                      color: "#F59E0B",
                    }}
                  >
                    {r}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* ─ Transaction Attributes ─ */}
          {hasAttributes && (
            <div className="pt-5">
              <SectionHead label="Transaction Attributes" />
              {row.timestamp      && <FieldRow label="Timestamp"         value={fmtTs(row.timestamp)} />}
              {row.country        && <FieldRow label="Country"            value={row.country} />}
              {row.payment_method && <FieldRow label="Payment Method"    value={row.payment_method} />}
              {row.merchant_category && (
                <FieldRow label="Merchant Category" value={row.merchant_category} />
              )}
              {deviceId && <FieldRow label="Device ID" value={deviceId} mono />}
            </div>
          )}

          {/* ─ Model and Rule Context ─ */}
          {hasModelContext && (
            <div className="pt-5">
              <SectionHead label="Model and Rule Context" />
              {row.model_prediction !== null && (
                <FieldRow
                  label="Model Prediction"
                  value={row.model_prediction === 1 ? "Flagged (1)" : "Clean (0)"}
                  valueColor={row.model_prediction === 1 ? "#F59E0B" : "#10B981"}
                />
              )}
              {row.rule_flag !== null && (
                <FieldRow
                  label="Rule Flag"
                  value={row.rule_flag === 1 ? "Triggered (1)" : "Not triggered (0)"}
                  valueColor={row.rule_flag === 1 ? "#F59E0B" : "#6B7280"}
                />
              )}
              {row.risk_tier && <FieldRow label="Risk Tier" value={row.risk_tier} />}
            </div>
          )}

          {/* ─ Scan Context ─ */}
          <div className="pt-5 pb-6">
            <SectionHead label="Scan Context" />
            {scanId   && <FieldRow label="Scan ID"     value={scanId}   mono />}
            {filename && <FieldRow label="Source File" value={filename} />}
            {row.promoted && row.promoted_case_id && (
              <FieldRow
                label="Promoted"
                value={`Case #${row.promoted_case_id}`}
                valueColor="#10B981"
              />
            )}
            {row.promoted_at && (
              <FieldRow label="Promoted At" value={fmtTs(row.promoted_at)} />
            )}
          </div>
        </div>

        {/* ── Actions footer ── */}
        <div
          className="shrink-0 space-y-2 px-5 py-4"
          style={{ borderTop: "1px solid rgba(255,255,255,0.08)" }}
        >
          {/* Case dossier link or promote button */}
          {row.validation_status === "VALID" && row.promoted && row.promoted_case_id ? (
            <Link
              href={`/cases/${row.promoted_case_id}`}
              className="flex w-full items-center justify-center rounded-md py-2 text-[12px] font-semibold"
              style={{
                background: "rgba(16,185,129,0.08)",
                border: "1px solid rgba(16,185,129,0.22)",
                color: "#10B981",
              }}
            >
              Open Case Dossier #{row.promoted_case_id}
            </Link>
          ) : row.validation_status === "VALID" ? (
            <button
              type="button"
              onClick={() => onPromote(row)}
              disabled={isPromoting}
              className="w-full rounded-md py-2 text-[12px] font-semibold"
              style={{
                background: isPromoting ? "rgba(34,211,238,0.03)" : "rgba(34,211,238,0.08)",
                border: "1px solid rgba(34,211,238,0.22)",
                color: isPromoting ? "#4B5563" : "#22D3EE",
                cursor: isPromoting ? "not-allowed" : "pointer",
              }}
            >
              {isPromoting ? "Promoting…" : "Promote to Case"}
            </button>
          ) : null}

          {/* Copy transaction ID */}
          {row.transaction_id && (
            <button
              type="button"
              onClick={handleCopyTxId}
              className="w-full rounded-md py-2 text-[12px]"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.09)",
                color: "#8B949E",
                cursor: "pointer",
              }}
            >
              Copy Transaction ID
            </button>
          )}

          {/* Close */}
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-md py-2 text-[12px]"
            style={{
              background: "rgba(255,255,255,0.025)",
              border: "1px solid rgba(255,255,255,0.07)",
              color: "#6B7280",
              cursor: "pointer",
            }}
          >
            Close
          </button>
        </div>
      </aside>
    </>
  );
}
