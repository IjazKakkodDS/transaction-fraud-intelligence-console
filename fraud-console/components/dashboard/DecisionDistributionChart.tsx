"use client";

import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { type DailySummary } from "@/types/workflow";

const DECISION_COLORS: Record<string, string> = {
  APPROVE: "#10B981",
  REVIEW: "#F59E0B",
  BLOCK: "#FF4D4D",
};

const DECISION_BG: Record<string, string> = {
  APPROVE: "rgba(16,185,129,0.10)",
  REVIEW: "rgba(245,158,11,0.10)",
  BLOCK: "rgba(255,77,77,0.10)",
};

interface DecisionDistributionChartProps {
  summary: DailySummary;
}

export function DecisionDistributionChart({ summary }: DecisionDistributionChartProps) {
  const data = [
    { decision: "APPROVE", count: summary.total_approve },
    { decision: "REVIEW", count: summary.total_review },
    { decision: "BLOCK", count: summary.total_block },
  ];
  const total = data.reduce((sum, item) => sum + item.count, 0);
  const pct = (n: number) => (total > 0 ? Math.round((n / total) * 100) : 0);

  return (
    <div className="card h-full p-4">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <p className="section-label">Decision Mix</p>
          <p className="mt-1 text-[12px]" style={{ color: "#CBD5E1" }}>
            {total.toLocaleString()} decisions recorded
          </p>
        </div>
      </div>

      {total === 0 ? (
        <div
          className="flex h-[190px] items-center justify-center rounded-lg text-[13px]"
          style={{
            background: "rgba(255,255,255,0.025)",
            border: "1px solid rgba(148,163,184,0.12)",
            color: "#94A3B8",
          }}
        >
          No decisions recorded yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_200px]">
          <div className="relative min-w-0" style={{ height: 190, minWidth: 0 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data}
                  dataKey="count"
                  nameKey="decision"
                  cx="50%"
                  cy="47%"
                  innerRadius={50}
                  outerRadius={76}
                  paddingAngle={3}
                  stroke="rgba(2,6,23,0.95)"
                  strokeWidth={3}
                >
                  {data.map((entry) => (
                    <Cell
                      key={entry.decision}
                      fill={DECISION_COLORS[entry.decision]}
                      fillOpacity={0.86}
                    />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value, name) => [
                    `${Number(value).toLocaleString()} decisions`,
                    String(name),
                  ]}
                  contentStyle={{
                    fontSize: 13,
                    background: "#111827",
                    border: "1px solid rgba(148,163,184,0.20)",
                    borderRadius: 6,
                    color: "#F8FAFC",
                    padding: "6px 10px",
                  }}
                  itemStyle={{ color: "#CBD5E1" }}
                  labelStyle={{ color: "#CBD5E1" }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-[22px] font-semibold tabular-nums" style={{ color: "#F8FAFC" }}>
                {total.toLocaleString()}
              </span>
              <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: "#94A3B8" }}>
                Total Decisions
              </span>
            </div>
          </div>

          <div className="flex flex-col justify-center gap-2">
            {data.map(({ decision, count }) => (
              <div
                key={decision}
                className="rounded-md px-3 py-1.5"
                style={{
                  background: DECISION_BG[decision],
                  border: `1px solid ${DECISION_COLORS[decision]}35`,
                }}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: DECISION_COLORS[decision] }}
                    />
                    <span className="text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: DECISION_COLORS[decision] }}>
                      {decision}
                    </span>
                  </div>
                  <span className="text-[12px] font-semibold tabular-nums" style={{ color: "#CBD5E1" }}>
                    {pct(count)}%
                  </span>
                </div>
                <p className="mt-1 text-[12px] tabular-nums" style={{ color: "#94A3B8" }}>
                  {count.toLocaleString()} cases
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
