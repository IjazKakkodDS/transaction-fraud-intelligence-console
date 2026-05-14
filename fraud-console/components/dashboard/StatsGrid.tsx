import {
  Layers,
  Clock,
  ShieldX,
  CheckCircle2,
  RotateCcw,
  AlertOctagon,
} from "lucide-react";
import { type DailySummary } from "@/types/workflow";

type Accent = "danger" | "warn" | "success" | "neutral";

interface AccentCfg {
  num: string;
  topBorder: string;
  bg: string;
  label: string;
  iconColor: string;
}

const ACCENT_CONFIG: Record<Accent, AccentCfg> = {
  danger: {
    num: "#FF4D4D",
    topBorder: "rgba(255,77,77,0.70)",
    bg: "rgba(255,77,77,0.06)",
    label: "rgba(255,77,77,0.55)",
    iconColor: "rgba(255,77,77,0.45)",
  },
  warn: {
    num: "#F59E0B",
    topBorder: "rgba(245,158,11,0.70)",
    bg: "rgba(245,158,11,0.06)",
    label: "rgba(245,158,11,0.55)",
    iconColor: "rgba(245,158,11,0.45)",
  },
  success: {
    num: "#10B981",
    topBorder: "rgba(16,185,129,0.65)",
    bg: "rgba(16,185,129,0.05)",
    label: "rgba(16,185,129,0.50)",
    iconColor: "rgba(16,185,129,0.40)",
  },
  neutral: {
    num: "#F0F6FC",
    topBorder: "transparent",
    bg: "transparent",
    label: "#94A3B8",
    iconColor: "#64748B",
  },
};

interface StatCardProps {
  label: string;
  value: number;
  accent?: Accent;
  pct?: number;
  Icon: React.ElementType;
}

function StatCard({ label, value, accent = "neutral", pct, Icon }: StatCardProps) {
  const effective: Accent = accent !== "neutral" && value > 0 ? accent : "neutral";
  const cfg = ACCENT_CONFIG[effective];

  return (
    <div
      className="card-metric flex flex-col gap-2 p-4"
      style={
        effective !== "neutral"
          ? {
              borderTop: `2px solid ${cfg.topBorder}`,
              background: `linear-gradient(160deg, ${cfg.bg} 0%, #0D1117 70%)`,
            }
          : { borderTop: "2px solid transparent" }
      }
    >
      <div className="flex items-start justify-between">
        <p
          className="metric-number"
          style={{ color: cfg.num, fontSize: "28px" }}
        >
          {value.toLocaleString()}
        </p>
        <Icon className="h-4 w-4 shrink-0 mt-0.5" style={{ color: cfg.iconColor }} />
      </div>
      <div>
        <p className="metric-label" style={{ color: cfg.label }}>
          {label}
        </p>
        {pct !== undefined && effective !== "neutral" && (
          <p
            className="mt-0.5 font-mono text-[10px]"
            style={{ color: cfg.iconColor }}
          >
            {pct.toFixed(1)}% of decisions
          </p>
        )}
      </div>
    </div>
  );
}

interface StatsGridProps {
  summary: DailySummary;
}

export function StatsGrid({ summary }: StatsGridProps) {
  const decisionTotal =
    summary.total_approve + summary.total_review + summary.total_block;
  const pct = (n: number) =>
    decisionTotal > 0 ? (n / decisionTotal) * 100 : 0;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <StatCard
        label="Total Cases"
        value={summary.total_cases}
        Icon={Layers}
      />
      <StatCard
        label="Under Review"
        value={summary.total_review}
        accent={summary.total_review > 0 ? "warn" : "neutral"}
        pct={pct(summary.total_review)}
        Icon={RotateCcw}
      />
      <StatCard
        label="Block Signals"
        value={summary.total_block}
        accent={summary.total_block > 0 ? "danger" : "neutral"}
        pct={pct(summary.total_block)}
        Icon={ShieldX}
      />
      <StatCard
        label="Approved"
        value={summary.total_approve}
        accent={summary.total_approve > 0 ? "success" : "neutral"}
        pct={pct(summary.total_approve)}
        Icon={CheckCircle2}
      />
      <StatCard
        label="Unreviewed"
        value={summary.unreviewed_cases}
        accent={summary.unreviewed_cases > 0 ? "warn" : "neutral"}
        Icon={Clock}
      />
      <StatCard
        label="Confirmed Fraud"
        value={summary.confirmed_fraud}
        accent={summary.confirmed_fraud > 0 ? "danger" : "neutral"}
        Icon={AlertOctagon}
      />
    </div>
  );
}
