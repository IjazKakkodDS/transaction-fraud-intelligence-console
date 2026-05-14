"use client";

import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { type SourceBreakdownItem } from "@/types/workflow";
import { formatLabel } from "@/lib/utils";

const SOURCE_COLORS: Record<string, string> = {
  Automation: "#A78BFA",
  API: "#22D3EE",
  Manual: "#8B949E",
};

function getSourceLabel(source: string): string {
  const lower = source.toLowerCase();
  if (lower.includes("n8n")) return "Automation";
  if (lower.includes("fastapi") || lower.includes("api")) return "API";
  if (lower.includes("manual")) return "Manual";
  return formatLabel(source);
}

export function SourceBreakdownChart({ data }: { data: SourceBreakdownItem[] }) {
  const aggregated = Object.values(
    data.reduce<Record<string, SourceBreakdownItem>>((acc, item) => {
      const label = getSourceLabel(item.source);
      acc[label] = acc[label] ?? { source: label, count: 0 };
      acc[label].count += item.count;
      return acc;
    }, {})
  );
  const total = aggregated.reduce((sum, item) => sum + item.count, 0);
  const automation = aggregated.find((item) => item.source === "Automation")?.count ?? 0;
  const automationCoverage = total > 0 ? Math.round((automation / total) * 100) : 0;

  return (
    <div className="card p-5">
      <p className="section-label mb-1">Source Coverage</p>
      <p className="mb-4 text-[12px]" style={{ color: "#94A3B8" }}>
        Where workflow events originate across the automation layer
      </p>
      {total === 0 ? (
        <p className="text-[13px]" style={{ color: "#94A3B8" }}>No source data recorded yet.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          <div className="relative h-[178px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={aggregated}
                  dataKey="count"
                  nameKey="source"
                  cx="50%"
                  cy="50%"
                  innerRadius={52}
                  outerRadius={74}
                  paddingAngle={3}
                  stroke="rgba(2,6,23,0.95)"
                  strokeWidth={3}
                >
                  {aggregated.map((entry) => (
                    <Cell
                      key={entry.source}
                      fill={SOURCE_COLORS[entry.source] ?? "#8B949E"}
                      fillOpacity={0.84}
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value) => [`${value ?? ""}`, "Events"]}
                  contentStyle={{
                    fontSize: 12,
                    background: "#141D2B",
                    border: "1px solid rgba(255,255,255,0.10)",
                    borderRadius: 6,
                    color: "#C9D1D9",
                    padding: "6px 10px",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-[24px] font-semibold tabular-nums" style={{ color: "#C9D1D9" }}>
                {automationCoverage}%
              </span>
              <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em]" style={{ color: "#94A3B8" }}>
                Automation
              </span>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {["Automation", "API", "Manual"].map((source) => {
              const count = aggregated.find((item) => item.source === source)?.count ?? 0;
              return (
                <div
                  key={source}
                  className="rounded-md px-3 py-2"
                  style={{
                    background: "rgba(255,255,255,0.025)",
                    border: `1px solid ${(SOURCE_COLORS[source] ?? "#8B949E")}35`,
                  }}
                >
                  <p className="text-[12px] font-semibold" style={{ color: SOURCE_COLORS[source] ?? "#CBD5E1" }}>
                    {source}
                  </p>
                  <p className="mt-1 text-[13px] tabular-nums" style={{ color: "#CBD5E1" }}>
                    {count.toLocaleString()}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
