"use client";

import { use } from "react";
import Link from "next/link";
import { useCase } from "@/lib/hooks/useCase";
import { CaseHeader } from "@/components/cases/CaseHeader";
import { CaseScoreSummary } from "@/components/cases/CaseScoreSummary";
import { CaseEvidenceGroups } from "@/components/cases/CaseEvidenceGroups";
import { InvestigationPanel } from "@/components/cases/InvestigationPanel";
import { AnalystActionPanel } from "@/components/cases/AnalystActionPanel";
import { WorkflowNotifyButton } from "@/components/cases/WorkflowNotifyButton";
import { CaseWorkflowEvents } from "@/components/cases/CaseWorkflowEvents";

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-xl ${className ?? ""}`}
      style={{ background: "rgba(255,255,255,0.04)" }}
    />
  );
}

interface CasePageProps {
  params: Promise<{ id: string }>;
}

export default function CasePage({ params }: CasePageProps) {
  const { id } = use(params);
  const caseId = parseInt(id, 10);
  const isValidId = !isNaN(caseId) && caseId > 0;

  const { data, isLoading, isError } = useCase(isValidId ? caseId : 0);

  if (!isValidId) {
    return (
      <div className="mx-auto max-w-6xl">
        <div
          className="rounded-lg px-4 py-3 text-[13px]"
          style={{ background: "rgba(255,77,77,0.07)", border: "1px solid rgba(255,77,77,0.22)", color: "#FF4D4D" }}
        >
          Invalid case ID: <span className="font-mono">{id}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4">

      {/* Hero */}
      <div
        className="pb-4"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <p className="route-label mb-1">Case Dossier 2.0</p>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="page-hero-title">Case #{caseId}</h1>
          <Link
            href="/queue"
            className="text-[13px] font-medium"
            style={{ color: "#4B5563" }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = "#8B949E")}
            onMouseLeave={(e) => ((e.currentTarget as HTMLAnchorElement).style.color = "#4B5563")}
          >
            Back to Review Queue
          </Link>
        </div>
      </div>

      {isLoading && (
        <>
          <Skeleton className="h-24" />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-9">
            <div className="space-y-4 lg:col-span-6">
              <Skeleton className="h-64" />
              <Skeleton className="h-52" />
              <Skeleton className="h-48" />
            </div>
            <div className="space-y-4 lg:col-span-3">
              <Skeleton className="h-52" />
              <Skeleton className="h-44" />
            </div>
          </div>
        </>
      )}

      {isError && (
        <div
          className="rounded-lg px-4 py-3 text-[13px]"
          style={{ background: "rgba(255,77,77,0.07)", border: "1px solid rgba(255,77,77,0.22)", color: "#FF4D4D" }}
        >
          Could not load case <span className="font-mono">#{caseId}</span>.
          Check that the API is reachable and the case exists.
        </div>
      )}

      {data && (
        <>
          <CaseHeader caseData={data} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-9">

            {/* Main dossier evidence */}
            <div className="space-y-4 lg:col-span-6">
              <CaseScoreSummary caseData={data} />
              <CaseEvidenceGroups reasons={data.reasons} />
              <InvestigationPanel caseId={caseId} />
            </div>

            {/* Analyst decision and workflow */}
            <aside className="space-y-4 lg:col-span-3">
              <AnalystActionPanel
                caseId={caseId}
                currentAnalystStatus={data.analyst_status}
                currentAnalystNotes={data.analyst_notes}
                reviewedAt={data.reviewed_at}
              />
              <div className="card p-5">
                <p className="section-label mb-4">Workflow Automation</p>
                <WorkflowNotifyButton caseId={caseId} />
                <div
                  className="mt-5 pt-4"
                  style={{ borderTop: "1px solid rgba(139,148,158,0.10)" }}
                >
                  <p className="section-label mb-3">Automation Audit Trail</p>
                  <CaseWorkflowEvents caseId={caseId} />
                </div>
              </div>
            </aside>

          </div>
        </>
      )}
    </div>
  );
}
