import { Activity, Network, Radar, Route, ShieldAlert } from "lucide-react";
import { classifyCaseEvidence } from "@/components/cases/caseEvidence";

interface EvidenceSectionProps {
  title: string;
  description: string;
  items: string[];
  icon: React.ReactNode;
  color: string;
}

function EvidenceSection({
  title,
  description,
  items,
  icon,
  color,
}: EvidenceSectionProps) {
  if (items.length === 0) return null;

  return (
    <section className="px-5 py-4" style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}>
      <div className="mb-3 flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-2.5">
          <span className="mt-0.5 shrink-0" style={{ color }}>
            {icon}
          </span>
          <div>
            <h3 className="text-[13px] font-semibold" style={{ color: "#D1D5DB" }}>
              {title}
            </h3>
            <p className="mt-0.5 text-[11px]" style={{ color: "#6B7280" }}>
              {description}
            </p>
          </div>
        </div>
        <span className="shrink-0 font-mono text-[12px] tabular-nums" style={{ color }}>
          {items.length}
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={item}
            className="inline-flex max-w-full items-center rounded px-2 py-1 text-[11px] font-medium leading-snug"
            style={{
              background: `${color}12`,
              border: `1px solid ${color}32`,
              color,
              overflowWrap: "anywhere",
            }}
          >
            {item}
          </span>
        ))}
      </div>
    </section>
  );
}

interface CaseEvidenceGroupsProps {
  reasons: string | string[] | null | undefined;
}

export function CaseEvidenceGroups({ reasons }: CaseEvidenceGroupsProps) {
  const evidence = classifyCaseEvidence(reasons);
  const total =
    evidence.base.length +
    evidence.rich.length +
    evidence.behavioural.length +
    evidence.graph.length +
    evidence.scenario.length;

  return (
    <section className="card overflow-hidden" aria-labelledby="intelligence-evidence-heading">
      <div className="px-5 py-4">
        <p className="section-label">Risk Evidence</p>
        <div className="mt-1 flex flex-wrap items-end justify-between gap-2">
          <h2 id="intelligence-evidence-heading" className="text-[16px] font-semibold" style={{ color: "#E5E7EB" }}>
            Intelligence evidence
          </h2>
          <span className="font-mono text-[11px] tabular-nums" style={{ color: "#6B7280" }}>
            {total} signal{total === 1 ? "" : "s"}
          </span>
        </div>
      </div>

      {total === 0 ? (
        <div
          className="px-5 py-5 text-[13px]"
          style={{ borderTop: "1px solid rgba(255,255,255,0.05)", color: "#6B7280" }}
        >
          No signal factors were recorded for this case.
        </div>
      ) : (
        <>
          <EvidenceSection
            title="Base Transaction Signals"
            description="Transaction-level model and deterministic rule evidence."
            items={evidence.base}
            icon={<ShieldAlert size={16} aria-hidden="true" />}
            color="#FF8080"
          />
          <EvidenceSection
            title="Rich Signals"
            description="Contextual transaction, device, velocity, and merchant evidence."
            items={evidence.rich}
            icon={<Radar size={16} aria-hidden="true" />}
            color="#F59E0B"
          />
          <EvidenceSection
            title="Behavioural Signals"
            description="Entity-aware deviations from customer or account baselines."
            items={evidence.behavioural}
            icon={<Activity size={16} aria-hidden="true" />}
            color="#93C5FD"
          />
          <EvidenceSection
            title="Graph Intelligence"
            description="Relationship-level device, account, and counterparty evidence."
            items={evidence.graph}
            icon={<Network size={16} aria-hidden="true" />}
            color="#A78BFA"
          />
          <EvidenceSection
            title="Scenario Context"
            description="Known scenario-family context recorded with the case evidence."
            items={evidence.scenario}
            icon={<Route size={16} aria-hidden="true" />}
            color="#22D3EE"
          />
        </>
      )}
    </section>
  );
}

