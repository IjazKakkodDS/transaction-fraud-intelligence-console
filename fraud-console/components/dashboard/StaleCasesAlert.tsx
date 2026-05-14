import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { type StaleCasesResponse } from "@/types/workflow";

interface StaleCasesAlertProps {
  data: StaleCasesResponse;
}

export function StaleCasesAlert({ data }: StaleCasesAlertProps) {
  if (data.count === 0) return null;

  return (
    <div
      className="flex items-center gap-3 rounded-lg px-4 py-3"
      style={{
        background: "rgba(245,158,11,0.07)",
        border: "1px solid rgba(245,158,11,0.22)",
        borderLeft: "3px solid rgba(245,158,11,0.80)",
        color: "#F59E0B",
      }}
    >
      <AlertTriangle className="h-5 w-5 shrink-0" />
      <span className="text-[13px]">
        <span className="font-semibold">{data.count}</span>{" "}
        {data.count === 1 ? "case" : "cases"} stale beyond {data.minutes} minutes.{" "}
        <Link href="/queue" className="font-semibold underline-offset-2 hover:underline">
          Open queue →
        </Link>
      </span>
    </div>
  );
}
