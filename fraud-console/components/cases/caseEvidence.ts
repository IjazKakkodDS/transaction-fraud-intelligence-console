export interface CaseEvidenceGroups {
  base: string[];
  rich: string[];
  behavioural: string[];
  graph: string[];
  scenario: string[];
}

const SCENARIO_LABELS: Record<string, string> = {
  "Account takeover pattern detected": "Account Takeover",
  "Card testing velocity pattern": "Card Testing",
  "High-velocity spend pattern": "High-Velocity Spend",
  "Unusual geographic pattern": "Unusual Geography",
  "New payee transfer risk": "New Payee Transfer",
  "Merchant risk spike": "Merchant Risk Spike",
  "Mule account behaviour pattern": "Mule Account",
  "Refund and chargeback abuse pattern": "Refund / Chargeback Abuse",
  "Dormant account reactivation detected": "Dormant Account Reactivation",
  "Cross-border high-value transaction": "Cross-Border High-Value",
  "Device mismatch detected": "Device Mismatch",
  "Suspicious repeated attempts detected": "Suspicious Repeated Attempts",
};

const RICH_LABELS: Record<string, string> = {
  LOW_TRUST_DEVICE: "Unrecognised device with low trust score",
  GEO_ANOMALY_DISTANCE: "Geographic location inconsistent with registered address",
  HIGH_1H_VELOCITY: "Transaction velocity exceeds 1-hour baseline",
  MULTIPLE_FAILED_ATTEMPTS: "Multiple failed attempts preceding this transaction",
  HIGH_RISK_MERCHANT: "High-risk merchant",
  NEW_PAYEE_TRANSFER: "First-time payment to unknown payee",
  PRIOR_CHARGEBACK_HISTORY: "High chargeback history",
  AMOUNT_ANOMALY_VS_30D: "Transaction amount significantly above 30-day average",
};

const RICH_REASON_TEXT = new Set(Object.values(RICH_LABELS));

const BEHAVIOURAL_LABELS: Record<string, string> = {
  BEHAVIOURAL_AMOUNT_DEVIATION: "Amount deviation",
  BEHAVIOURAL_VELOCITY_DEVIATION: "Velocity deviation",
  BALANCE_DROP_ANOMALY: "Balance drop anomaly",
  NEW_DEVICE_FOR_CUSTOMER: "New device for customer",
  NEW_COUNTRY_FOR_CUSTOMER: "New country for customer",
  NEW_COUNTERPARTY_FOR_ACCOUNT: "New counterparty for account",
  UNUSUAL_CHANNEL_FOR_CUSTOMER: "Unusual channel",
  BEHAVIOURAL_PROFILE_SHIFT: "Behavioural profile shift",
};

const GRAPH_LABELS: Record<string, string> = {
  SHARED_DEVICE_CLUSTER: "Shared device cluster",
  DEVICE_ACCOUNT_REUSE: "Device reuse across accounts",
  MULE_FAN_IN_PATTERN: "Mule fan-in pattern",
  MULE_FAN_OUT_PATTERN: "Mule fan-out pattern",
};

function unique(items: string[]): string[] {
  return [...new Set(items)];
}

export function classifyCaseEvidence(
  reasons: string | string[] | null | undefined,
): CaseEvidenceGroups {
  const values = Array.isArray(reasons)
    ? reasons
    : reasons?.split("|") ?? [];

  const groups: CaseEvidenceGroups = {
    base: [],
    rich: [],
    behavioural: [],
    graph: [],
    scenario: [],
  };

  for (const rawReason of values) {
    const reason = rawReason.trim();
    if (!reason) continue;

    if (reason in SCENARIO_LABELS) {
      groups.scenario.push(SCENARIO_LABELS[reason]);
    } else if (reason in RICH_LABELS) {
      groups.rich.push(RICH_LABELS[reason]);
    } else if (RICH_REASON_TEXT.has(reason)) {
      groups.rich.push(reason);
    } else if (reason in BEHAVIOURAL_LABELS) {
      groups.behavioural.push(BEHAVIOURAL_LABELS[reason]);
    } else if (reason in GRAPH_LABELS) {
      groups.graph.push(GRAPH_LABELS[reason]);
    } else {
      groups.base.push(reason);
    }
  }

  return {
    base: unique(groups.base),
    rich: unique(groups.rich),
    behavioural: unique(groups.behavioural),
    graph: unique(groups.graph),
    scenario: unique(groups.scenario),
  };
}

