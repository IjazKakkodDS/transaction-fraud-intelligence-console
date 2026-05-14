"use client";

import { type AnalystStatus } from "@/types/case";

const FILTERS: { label: string; value: AnalystStatus }[] = [
  { label: "All Cases",       value: null             },
  { label: "Unreviewed",      value: "UNREVIEWED"     },
  { label: "Confirmed Fraud", value: "CONFIRMED_FRAUD" },
  { label: "False Positive",  value: "FALSE_POSITIVE"  },
  { label: "Approved",        value: "APPROVED"        },
];

interface QueueFiltersProps {
  selected: AnalystStatus;
  onChange: (value: AnalystStatus) => void;
}

export function QueueFilters({ selected, onChange }: QueueFiltersProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {FILTERS.map(({ label, value }) => {
          const active = selected === value;
          return (
            <button
              key={label}
              onClick={() => onChange(value)}
              className="rounded-md px-3.5 py-2 text-[13px] font-medium transition-colors"
              style={
                active
                  ? {
                      background: "rgba(34,211,238,0.12)",
                      border: "1px solid rgba(34,211,238,0.30)",
                      color: "#22D3EE",
                    }
                  : {
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(255,255,255,0.08)",
                      color: "#8B949E",
                    }
              }
            >
              {label}
            </button>
          );
        })}
    </div>
  );
}
