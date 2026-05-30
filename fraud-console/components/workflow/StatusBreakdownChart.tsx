"use client";

import {
  Cell,
  Pie,
  PieChart,
  Tooltip,
} from "recharts";
import { MeasuredChartFrame } from "@/components/charts/MeasuredChartFrame";
import { type StatusBreakdownItem } from "@/types/workflow";

const STATUS_COLORS: Record<string, string> = {
  Success: "#10B981",
  Failed: "#FF4D4D",
};

function getStatusLabel(status: string): string {
  return status.toUpperCase() === "SUCCESS" ? "Success" : status.toUpperCase() === "FAILED" ? "Failed" : status;
}

export function StatusBreakdownChart({ data }: { data: StatusBreakdownItem[] }) {
  const chartData = data.map((item) => ({
    status: getStatusLabel(item.status),
    count: item.count,
  }));
  const total = chartData.reduce((sum, item) => sum + item.count, 0);
  const success = chartData.find((item) => item.status === "Success")?.count ?? 0;
  const successRate = total > 0 ? Math.round((success / total) * 100) : 0;

  return (
    <div className="card p-5">
      <p className="section-label mb-1">Reliability Outcome</p>
      <p className="mb-4 text-[12px]" style={{ color: "#94A3B8" }}>
        Successful versus failed automation outcomes
      </p>
      {total === 0 ? (
        <p className="text-[13px]" style={{ color: "#94A3B8" }}>No status data recorded yet.</p>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          <MeasuredChartFrame height={178} className="relative">
            {({ width, height }) => (
              <>
              <PieChart width={width} height={height}>
                <Pie
                  data={chartData}
                  dataKey="count"
                  nameKey="status"
                  cx="50%"
                  cy="50%"
                  innerRadius={52}
                  outerRadius={74}
                  paddingAngle={3}
                  stroke="rgba(2,6,23,0.95)"
                  strokeWidth={3}
                >
                  {chartData.map((entry) => (
                    <Cell
                      key={entry.status}
                      fill={STATUS_COLORS[entry.status] ?? "#8B949E"}
                      fillOpacity={0.86}
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
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-[24px] font-semibold tabular-nums" style={{ color: "#C9D1D9" }}>
                  {successRate}%
                </span>
                <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em]" style={{ color: "#94A3B8" }}>
                  Success Rate
                </span>
              </div>
              </>
            )}
          </MeasuredChartFrame>
          <div className="grid grid-cols-2 gap-2">
            {chartData.map((item) => (
              <div
                key={item.status}
                className="rounded-md px-3 py-2"
                style={{
                  background: "rgba(255,255,255,0.025)",
                  border: `1px solid ${(STATUS_COLORS[item.status] ?? "#8B949E")}35`,
                }}
              >
                <p className="text-[12px] font-semibold" style={{ color: STATUS_COLORS[item.status] ?? "#CBD5E1" }}>
                  {item.status}
                </p>
                <p className="mt-1 text-[13px] tabular-nums" style={{ color: "#CBD5E1" }}>
                  {item.count.toLocaleString()} events
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
