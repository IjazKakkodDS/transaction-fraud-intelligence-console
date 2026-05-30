"use client";

import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { MeasuredChartFrame } from "@/components/charts/MeasuredChartFrame";
import { type ActionBreakdownItem } from "@/types/workflow";
import { formatLabel } from "@/lib/utils";

const ACTION_LABEL_MAP: Record<string, string> = {
  WORKFLOW_DISPATCH_FAILED:  "Dispatch Failed",
  ESCALATE_TO_FRAUD_OPS:     "Escalate To Fraud Ops",
  DAILY_FRAUD_OPS_SUMMARY:   "Daily Fraud Ops Summary",
  STALE_CASE_REMINDER:       "Stale Case Reminder",
  SEND_STALE_CASE_REMINDER:  "Stale Case Reminder",
};

function getActionLabel(action: string): string {
  return ACTION_LABEL_MAP[action.toUpperCase()] ?? formatLabel(action);
}

interface ActionBreakdownChartProps {
  data: ActionBreakdownItem[];
}

export function ActionBreakdownChart({ data }: ActionBreakdownChartProps) {
  const sorted = [...data].sort((a, b) => b.count - a.count);
  const getBarColor = (action: string) =>
    action.toUpperCase().includes("FAILED") ? "#FF4D4D" : "#22D3EE";
  const chartHeight = Math.max(180, sorted.length * 38);

  return (
    <div className="card p-5">
      <p className="section-label mb-1">Failure & Action Concentration</p>
      <p className="mb-4 text-[12px]" style={{ color: "#94A3B8" }}>
        Workflow actions contributing most to automation activity
      </p>
      {sorted.length === 0 ? (
        <p className="text-[13px]" style={{ color: "#94A3B8" }}>No action data recorded yet.</p>
      ) : (
        <MeasuredChartFrame height={chartHeight}>
          {({ width, height }) => (
          <BarChart
            width={width}
            height={height}
            data={sorted}
            layout="vertical"
            margin={{ left: 8, right: 16, top: 4, bottom: 4 }}
            barCategoryGap="30%"
          >
            <XAxis
              type="number"
              allowDecimals={false}
              tick={{ fontSize: 11, fill: "#94A3B8" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="workflow_action"
              width={180}
              tick={{ fontSize: 11, fill: "#8B949E" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={getActionLabel}
            />
            <Tooltip
              cursor={{ fill: "rgba(34,211,238,0.04)" }}
              contentStyle={{
                fontSize: 12,
                background: "#141D2B",
                border: "1px solid rgba(255,255,255,0.10)",
                borderRadius: 6,
                color: "#C9D1D9",
                padding: "6px 10px",
              }}
              labelFormatter={(label) => getActionLabel(String(label ?? ""))}
              formatter={(value) => [`${value ?? ""}`, "Events"]}
            />
            <Bar dataKey="count" fillOpacity={0.76} radius={[0, 3, 3, 0]}>
              {sorted.map((entry) => (
                <Cell key={entry.workflow_action} fill={getBarColor(entry.workflow_action)} />
              ))}
            </Bar>
          </BarChart>
          )}
        </MeasuredChartFrame>
      )}
    </div>
  );
}
