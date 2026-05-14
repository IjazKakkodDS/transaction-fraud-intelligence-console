"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

interface CaseRowActionsProps {
  caseId: number;
}

export function CaseRowActions({ caseId }: CaseRowActionsProps) {
  const [hovered, setHovered] = useState(false);
  return (
    <Link
      href={`/cases/${caseId}`}
      className="inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-[13px] font-medium transition-colors whitespace-nowrap"
      style={{
        background: hovered ? "rgba(34,211,238,0.14)" : "rgba(34,211,238,0.08)",
        border: hovered ? "1px solid rgba(34,211,238,0.40)" : "1px solid rgba(34,211,238,0.22)",
        color: "#22D3EE",
        minHeight: "36px",
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      Open Dossier
      <ArrowRight className="h-3.5 w-3.5" />
    </Link>
  );
}
