"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { fetchScoredTransaction, submitTransaction } from "@/lib/api/intake";
import { type IntakePayload } from "@/types/intake";
import { type Prediction } from "@/types/case";
import { IntakeForm } from "@/components/intake/IntakeForm";
import { ScoreResult } from "@/components/intake/ScoreResult";

type IntakePhase =
  | { tag: "idle" }
  | { tag: "confirming"; payload: IntakePayload }
  | { tag: "submitting" }
  | { tag: "polling"; transactionId: string }
  | { tag: "result"; prediction: Prediction }
  | { tag: "timeout"; transactionId: string }
  | { tag: "error"; message: string };

function wait(delayMs: number) {
  return new Promise((resolve) => {
    setTimeout(resolve, delayMs);
  });
}

async function pollForResult(
  transactionId: string,
  attempts = 5,
  delayMs = 800,
): Promise<Prediction | null> {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const prediction = await fetchScoredTransaction(transactionId);
    if (prediction) return prediction;
    if (attempt < attempts - 1) await wait(delayMs);
  }
  return null;
}

function LoadingCard({ label }: { label: string }) {
  return (
    <div className="card space-y-4 p-5">
      <p className="section-label">{label}</p>
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, index) => (
          <div
            key={index}
            className="h-10 animate-pulse rounded-md"
            style={{ background: "rgba(255,255,255,0.04)" }}
          />
        ))}
      </div>
    </div>
  );
}

function activeWorkflowStep(phase: IntakePhase["tag"]) {
  if (phase === "confirming") return "Confirm Submission";
  if (phase === "submitting" || phase === "polling") return "Risk Scoring";
  if (phase === "result" || phase === "timeout") return "Case Handoff";
  return "Enter Details";
}

function WorkflowStrip({ phase }: { phase: IntakePhase }) {
  const active = activeWorkflowStep(phase.tag);
  const steps = ["Enter Details", "Confirm Submission", "Risk Scoring", "Case Handoff"];

  return (
    <div className="card overflow-hidden">
      <div className="grid grid-cols-2 md:grid-cols-4">
        {steps.map((step, index) => {
          const isActive = step === active;
          return (
            <div
              key={step}
              className="px-4 py-3"
              style={{
                background: isActive ? "rgba(34,211,238,0.08)" : "transparent",
                borderRight: "1px solid rgba(255,255,255,0.05)",
                borderBottom: isActive ? "1px solid rgba(34,211,238,0.28)" : "1px solid rgba(255,255,255,0.04)",
              }}
            >
              <p className="font-mono text-[12px] font-semibold" style={{ color: isActive ? "#22D3EE" : "#6B7280" }}>
                {String(index + 1).padStart(2, "0")}
              </p>
              <p className="mt-1 text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: isActive ? "#C9D1D9" : "#8B949E" }}>
                {step}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function IntakeMissionPanel() {
  const cells = [
    {
      title: "Input Quality",
      text: "Complete scoring fields before submission.",
    },
    {
      title: "Score Accuracy",
      text: "Amount, timing, payment rail, geography, merchant, and device context influence risk.",
    },
    {
      title: "Case Handoff",
      text: "Scored transactions become reviewable cases with investigation and audit traceability.",
    },
  ];

  return (
    <section className="card overflow-hidden">
      <div className="px-4 py-3" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <p className="section-label">Intake Workflow</p>
        <p className="mt-1 text-[12px]" style={{ color: "#8B949E" }}>
          Submit a transaction, generate a risk outcome, and continue into the case review lifecycle.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3">
        {cells.map((cell) => (
          <div
            key={cell.title}
            className="px-4 py-3"
            style={{ borderRight: "1px solid rgba(255,255,255,0.05)" }}
          >
            <p className="metric-label">{cell.title}</p>
            <p className="mt-1.5 text-[12px] leading-snug" style={{ color: "#C9D1D9" }}>
              {cell.text}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function ConfirmationPanel({
  payload,
  onConfirm,
  onEdit,
}: {
  payload: IntakePayload;
  onConfirm: (payload: IntakePayload) => void;
  onEdit: () => void;
}) {
  const groupStyle = {
    background: "rgba(255,255,255,0.02)",
    border: "1px solid rgba(255,255,255,0.07)",
    borderRadius: "8px",
    padding: "12px",
  };

  const rowStyle = {
    background: "rgba(255,255,255,0.035)",
    border: "1px solid rgba(255,255,255,0.07)",
  };

  const scoringRows = [
    { label: "Amount", value: `${payload.amount} ${payload.currency}` },
    { label: "Timestamp", value: payload.timestamp },
    { label: "Payment Method", value: payload.payment_method },
    { label: "Country", value: payload.country },
    { label: "Merchant Category", value: payload.merchant_category ?? "Not provided" },
    { label: "International", value: payload.is_international ? "Yes" : "No" },
    { label: "Device ID", value: payload.device_id ?? "Not provided" },
    { label: "Device Type", value: payload.device_type ?? "Not provided" },
  ];

  const identityRows = [
    { label: "Transaction ID", value: payload.transaction_id },
    { label: "User ID", value: payload.user_id },
    { label: "Merchant ID", value: payload.merchant_id },
    { label: "Currency", value: payload.currency },
  ];

  const investigationRows = [
    payload.city ? { label: "City", value: payload.city } : null,
    payload.ip_address ? { label: "IP Address", value: payload.ip_address } : null,
  ].filter((row): row is { label: string; value: string } => row !== null);

  return (
    <section className="card space-y-5 p-5">
      <div>
        <p className="section-label">Review Transaction Submission</p>
        <p className="mt-2 text-[13px] leading-relaxed" style={{ color: "#C9D1D9" }}>
          Confirm the scoring inputs and traceability fields before sending the transaction into the fraud lifecycle.
        </p>
      </div>

      {/* Scoring Inputs */}
      <div style={groupStyle}>
        <p className="section-label mb-3">Scoring Inputs</p>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {scoringRows.map((row) => (
            <div key={row.label} className="rounded-md px-3 py-2.5" style={rowStyle}>
              <p className="metric-label">{row.label}</p>
              <p className="mt-1 break-words text-[13px]" style={{ color: "#C9D1D9" }}>
                {row.value}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Transaction Identity */}
      <div style={groupStyle}>
        <p className="section-label mb-3">Transaction Identity</p>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {identityRows.map((row) => (
            <div key={row.label} className="rounded-md px-3 py-2.5" style={rowStyle}>
              <p className="metric-label">{row.label}</p>
              <p className="mt-1 break-words text-[13px]" style={{ color: "#C9D1D9" }}>
                {row.value}
              </p>
            </div>
          ))}
        </div>
      </div>

      {investigationRows.length > 0 && (
        <div style={groupStyle}>
          <p className="section-label mb-3">Investigation Context</p>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {investigationRows.map((row) => (
              <div key={row.label} className="rounded-md px-3 py-2.5" style={rowStyle}>
                <p className="metric-label">{row.label}</p>
                <p className="mt-1 break-words text-[13px]" style={{ color: "#C9D1D9" }}>
                  {row.value}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div
        className="rounded-md px-3 py-2.5 text-[12px]"
        style={{
          background: "rgba(245,158,11,0.06)",
          border: "1px solid rgba(245,158,11,0.18)",
          color: "#C9D1D9",
        }}
      >
        Once submitted, the transaction will enter risk scoring and case handoff.
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => onConfirm(payload)}
          className="rounded-md px-4 py-2.5 text-[13px] font-semibold"
          style={{
            background: "rgba(34,211,238,0.10)",
            border: "1px solid rgba(34,211,238,0.28)",
            color: "#22D3EE",
          }}
        >
          Confirm and Score
        </button>
        <button
          type="button"
          onClick={onEdit}
          className="rounded-md px-4 py-2.5 text-[13px] font-semibold"
          style={{
            background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.09)",
            color: "#C9D1D9",
          }}
        >
          Edit Details
        </button>
      </div>
    </section>
  );
}

export default function IntakePage() {
  const [phase, setPhase] = useState<IntakePhase>({ tag: "idle" });
  const [draftPayload, setDraftPayload] = useState<IntakePayload | null>(null);
  const mutation = useMutation({ mutationFn: submitTransaction });
  const isSubmitting = phase.tag === "submitting" || phase.tag === "polling";

  function handleValidatedPayload(payload: IntakePayload) {
    setDraftPayload(payload);
    setPhase({ tag: "confirming", payload });
  }

  async function confirmAndSubmit(payload: IntakePayload) {
    try {
      setPhase({ tag: "submitting" });
      await mutation.mutateAsync(payload);
      setPhase({ tag: "polling", transactionId: payload.transaction_id });
      const prediction = await pollForResult(payload.transaction_id);
      if (prediction) {
        setPhase({ tag: "result", prediction });
      } else {
        setPhase({ tag: "timeout", transactionId: payload.transaction_id });
      }
    } catch {
      setPhase({
        tag: "error",
        message: "Could not submit transaction. Check API connectivity.",
      });
    }
  }

  function reset() {
    mutation.reset();
    setDraftPayload(null);
    setPhase({ tag: "idle" });
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div
        className="pb-4"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}
      >
        <p className="route-label mb-1.5">Transaction Processing</p>
        <h1 className="page-hero-title">Transaction Intake</h1>
        <p
          className="mt-1 text-[13px] leading-relaxed"
          style={{ color: "#4B5563", maxWidth: "560px" }}
        >
          Submit a single transaction for real-time fraud scoring and immediate risk assessment.
        </p>
      </div>

      <WorkflowStrip phase={phase} />
      <IntakeMissionPanel />

      {phase.tag === "error" && (
        <div
          className="rounded-lg px-4 py-3 text-[13px]"
          style={{
            background: "rgba(255,77,77,0.07)",
            border: "1px solid rgba(255,77,77,0.22)",
            color: "#FF4D4D",
          }}
        >
          {phase.message}
        </div>
      )}

      {(phase.tag === "idle" || phase.tag === "error") && (
        <IntakeForm
          onSubmit={handleValidatedPayload}
          isSubmitting={isSubmitting}
          initialPayload={draftPayload ?? undefined}
        />
      )}

      {phase.tag === "confirming" && (
        <ConfirmationPanel
          payload={phase.payload}
          onConfirm={confirmAndSubmit}
          onEdit={() => setPhase({ tag: "idle" })}
        />
      )}

      {phase.tag === "submitting" && <LoadingCard label="Submitting transaction..." />}
      {phase.tag === "polling" && <LoadingCard label="Retrieving risk score..." />}

      {phase.tag === "result" && (
        <ScoreResult prediction={phase.prediction} onReset={reset} />
      )}

      {phase.tag === "timeout" && (
        <div
          className="card space-y-4 p-5"
          style={{
            border: "1px solid rgba(245,158,11,0.24)",
            background: "rgba(245,158,11,0.055)",
          }}
        >
          <p className="section-label" style={{ color: "#F59E0B" }}>
            Scoring In Progress
          </p>
          <p className="text-[13px] leading-relaxed" style={{ color: "#C9D1D9" }}>
            The transaction has been submitted and scoring may still be processing. Check the Review Queue shortly for cases requiring analyst review.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/queue"
              className="rounded-md px-4 py-2.5 text-[13px] font-semibold"
              style={{
                background: "rgba(245,158,11,0.10)",
                border: "1px solid rgba(245,158,11,0.28)",
                color: "#F59E0B",
              }}
            >
              View Review Queue
            </Link>
            <button
              type="button"
              onClick={reset}
              className="rounded-md px-4 py-2.5 text-[13px] font-semibold"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.09)",
                color: "#C9D1D9",
              }}
            >
              Submit Another
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
