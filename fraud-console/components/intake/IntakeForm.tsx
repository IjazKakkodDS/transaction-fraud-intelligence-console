import { useState, type CSSProperties, type ChangeEvent, type FormEvent } from "react";
import { IntakePayloadSchema, type IntakePayload } from "@/types/intake";

type IntakeFormProps = {
  onSubmit: (payload: IntakePayload) => void;
  isSubmitting: boolean;
  initialPayload?: IntakePayload;
};

type IntakeFields = {
  transaction_id: string;
  user_id: string;
  merchant_id: string;
  amount: string;
  currency: string;
  payment_method: string;
  timestamp: string;
  country: string;
  city: string;
  device_id: string;
  ip_address: string;
  device_type: string;
  merchant_category: string;
  is_international: boolean;
};

const BASE_FIELD_STYLE: CSSProperties = {
  background: "rgba(255,255,255,0.04)",
  border: "1px solid rgba(255,255,255,0.09)",
  color: "#C9D1D9",
};

const ERROR_FIELD_STYLE: CSSProperties = {
  background: "rgba(255,77,77,0.06)",
  border: "1px solid rgba(255,77,77,0.65)",
  color: "#C9D1D9",
};

const SECTION_STYLE: CSSProperties = {
  background: "rgba(255,255,255,0.02)",
  border: "1px solid rgba(255,255,255,0.07)",
  borderRadius: "8px",
  padding: "16px",
};

const FRIENDLY_ERRORS: Record<string, string> = {
  transaction_id: "Transaction ID is required.",
  user_id: "User ID is required.",
  merchant_id: "Merchant ID is required.",
  amount: "Amount must be greater than zero.",
  currency: "Currency must be a 3-letter code.",
  payment_method: "Payment method is required.",
  timestamp: "Timestamp is required.",
  country: "Country must be a 2-letter code.",
};

const SIGNAL_CHIPS = [
  "High Amount",
  "Time of Day",
  "Payment Rail",
  "Region",
  "Merchant Category",
  "International",
  "Device Context",
];

function createTransactionId(prefix?: string) {
  const value =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2, 11);
  return prefix ? `${prefix}${value}` : value;
}

function createInitialFields(initialPayload?: IntakePayload): IntakeFields {
  if (initialPayload) {
    return {
      transaction_id: initialPayload.transaction_id,
      user_id: initialPayload.user_id,
      merchant_id: initialPayload.merchant_id,
      amount: String(initialPayload.amount),
      currency: initialPayload.currency,
      payment_method: initialPayload.payment_method,
      timestamp: initialPayload.timestamp,
      country: initialPayload.country,
      city: initialPayload.city ?? "",
      device_id: initialPayload.device_id ?? "",
      ip_address: initialPayload.ip_address ?? "",
      device_type: initialPayload.device_type ?? "",
      merchant_category: initialPayload.merchant_category ?? "",
      is_international: initialPayload.is_international ?? false,
    };
  }

  return {
    transaction_id: createTransactionId(),
    user_id: "",
    merchant_id: "",
    amount: "",
    currency: "USD",
    payment_method: "",
    timestamp: new Date().toISOString(),
    country: "US",
    city: "",
    device_id: "",
    ip_address: "",
    device_type: "",
    merchant_category: "",
    is_international: false,
  };
}

function optionalString(value: string) {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p className="mt-1.5 text-[12px] leading-snug" style={{ color: "#FF4D4D" }}>
      {message}
    </p>
  );
}

function RequiredChip() {
  return (
    <span
      className="ml-1.5 inline-block rounded px-1 py-[1px] text-[8.5px] font-semibold uppercase tracking-[0.08em]"
      style={{
        background: "rgba(34,211,238,0.055)",
        border: "1px solid rgba(34,211,238,0.12)",
        color: "rgba(34,211,238,0.78)",
      }}
    >
      required
    </span>
  );
}

function OptionalChip() {
  return (
    <span
      className="ml-1.5 inline-block rounded px-1 py-[1px] text-[8.5px] font-semibold uppercase tracking-[0.08em]"
      style={{
        background: "rgba(255,255,255,0.025)",
        border: "1px solid rgba(255,255,255,0.06)",
        color: "rgba(107,114,128,0.84)",
      }}
    >
      optional
    </span>
  );
}

export function IntakeForm({ onSubmit, isSubmitting, initialPayload }: IntakeFormProps) {
  const [fields, setFields] = useState<IntakeFields>(() => createInitialFields(initialPayload));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [showInvestigation, setShowInvestigation] = useState(false);

  function updateTextField(
    key: keyof Omit<IntakeFields, "is_international">,
    event: ChangeEvent<HTMLInputElement>,
  ) {
    setFields((current) => ({ ...current, [key]: event.target.value }));
    setErrors((current) => {
      if (!current[key]) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function buildPayload() {
    return {
      transaction_id: fields.transaction_id.trim(),
      user_id: fields.user_id.trim(),
      merchant_id: fields.merchant_id.trim(),
      amount: fields.amount,
      currency: fields.currency.trim().toUpperCase(),
      payment_method: fields.payment_method.trim(),
      timestamp: fields.timestamp.trim(),
      country: fields.country.trim().toUpperCase(),
      city: optionalString(fields.city),
      device_id: optionalString(fields.device_id),
      ip_address: optionalString(fields.ip_address),
      device_type: optionalString(fields.device_type),
      merchant_category: optionalString(fields.merchant_category),
      is_international: fields.is_international,
    };
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = IntakePayloadSchema.safeParse(buildPayload());
    if (!result.success) {
      const nextErrors: Record<string, string> = {};
      for (const issue of result.error.issues) {
        const key = String(issue.path[0]);
        if (!nextErrors[key]) {
          nextErrors[key] = FRIENDLY_ERRORS[key] ?? issue.message;
        }
      }
      setErrors(nextErrors);
      return;
    }
    setErrors({});
    onSubmit(result.data);
  }

  function fillHighRiskExample() {
    setFields({
      transaction_id: createTransactionId("txn_high_"),
      user_id: "user_high_001",
      merchant_id: "merchant_risk_001",
      amount: "2750",
      currency: "USD",
      payment_method: "credit_card",
      timestamp: "2026-05-09T02:15:00Z",
      country: "RU",
      city: "Moscow",
      device_id: "",
      ip_address: "",
      device_type: "mobile",
      merchant_category: "electronics",
      is_international: true,
    });
    setErrors({});
    setShowInvestigation(true);
  }

  function fillLowRiskExample() {
    setFields({
      transaction_id: createTransactionId("txn_low_"),
      user_id: "user_low_001",
      merchant_id: "merchant_regular_001",
      amount: "49.99",
      currency: "USD",
      payment_method: "debit_card",
      timestamp: "2026-05-09T14:30:00Z",
      country: "US",
      city: "New York",
      device_id: "device_001",
      ip_address: "192.168.1.10",
      device_type: "desktop",
      merchant_category: "groceries",
      is_international: false,
    });
    setErrors({});
    setShowInvestigation(true);
  }

  function clearFields() {
    setFields(createInitialFields());
    setErrors({});
  }

  function renderField(
    fieldKey: keyof Omit<IntakeFields, "is_international">,
    label: string,
    helper: string,
    required: boolean,
    type?: string,
  ) {
    const hasError = Boolean(errors[fieldKey]);
    return (
      <label className="block">
        <span className="mb-1 flex items-center">
          <span className="metric-label">{label}</span>
          {required ? <RequiredChip /> : <OptionalChip />}
        </span>
        <input
          type={type ?? "text"}
          value={fields[fieldKey]}
          onChange={(event) => updateTextField(fieldKey, event)}
          disabled={isSubmitting}
          className="w-full rounded-md px-3 py-2 text-[13px] focus:outline-none"
          style={hasError ? ERROR_FIELD_STYLE : BASE_FIELD_STYLE}
          step={fieldKey === "amount" ? "0.01" : undefined}
        />
        <p className="mt-1 text-[11px]" style={{ color: "#6B7280" }}>
          {helper}
        </p>
        <FieldError message={errors[fieldKey]} />
      </label>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="card space-y-5 p-5">

      <div
        className="rounded-md p-4"
        style={{
          background: "rgba(255,255,255,0.02)",
          border: "1px solid rgba(255,255,255,0.07)",
        }}
      >
        <p className="section-label">Scenario Launcher</p>
        <p className="mt-1.5 text-[12px]" style={{ color: "#8B949E" }}>
          Use controlled scenarios to validate scoring behavior before manual entry.
        </p>
        <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
          {[
            {
              label: "High-Risk Scenario",
              text: "Night, high-value, international, risky merchant.",
              onClick: fillHighRiskExample,
              color: "#FF4D4D",
            },
            {
              label: "Low-Risk Scenario",
              text: "Low amount, domestic, known device context.",
              onClick: fillLowRiskExample,
              color: "#10B981",
            },
            {
              label: "Clear Workspace",
              text: "Reset form values and validation state.",
              onClick: clearFields,
              color: "#8B949E",
            },
          ].map((action) => (
            <button
              key={action.label}
              type="button"
              onClick={action.onClick}
              disabled={isSubmitting}
              className="rounded-md px-3 py-3 text-left disabled:cursor-not-allowed disabled:opacity-45"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.09)",
              }}
            >
              <span className="block text-[12px] font-semibold" style={{ color: action.color }}>
                {action.label}
              </span>
              <span className="mt-1 block text-[11px] leading-snug" style={{ color: "#8B949E" }}>
                {action.text}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Section A: Scoring Inputs */}
      <div
        className="space-y-4"
        style={{
          ...SECTION_STYLE,
          borderTop: "2px solid rgba(34,211,238,0.36)",
          boxShadow: "inset 3px 0 0 rgba(34,211,238,0.24)",
        }}
      >
        <div>
          <p className="section-label">Scoring Inputs</p>
          <p className="mt-1 text-[12px]" style={{ color: "#8B949E" }}>
            These fields influence the enhanced fraud score through the model, deterministic rules, or reason-code generation.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <span className="metric-label mr-1">Signals evaluated</span>
            {SIGNAL_CHIPS.map((chip) => (
              <span
                key={chip}
                className="rounded px-2 py-1 text-[10.5px]"
                style={{
                  background: "rgba(34,211,238,0.055)",
                  border: "1px solid rgba(34,211,238,0.12)",
                  color: "#8B949E",
                }}
              >
                {chip}
              </span>
            ))}
          </div>
        </div>

        {/* Scoring contract callout */}
        <div
          className="rounded-md p-3"
          style={{
            background: "rgba(34,211,238,0.04)",
            border: "1px solid rgba(34,211,238,0.12)",
          }}
        >
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.1em]"
            style={{ color: "#22D3EE" }}
          >
            Enhanced Scoring Contract
          </p>
          <p className="mt-1.5 text-[12px] leading-relaxed" style={{ color: "#8B949E" }}>
            The scoring engine combines model output and deterministic rule signals. Amount, transaction time, payment method, country, merchant category, international status, and device context can influence the final risk outcome.
          </p>
          <p className="mt-2 font-mono text-[11px]" style={{ color: "#6B7280" }}>
            Risk score = 0.6 model output + 0.4 rule flag
          </p>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {renderField(
            "amount",
            "Amount",
            "Transaction value. High-value transactions may increase risk.",
            true,
            "number",
          )}
          {renderField(
            "timestamp",
            "Timestamp",
            "ISO timestamp for when the transaction occurred. Night-time activity can increase risk.",
            true,
          )}
          {renderField(
            "payment_method",
            "Payment Method",
            "Use values such as credit_card, debit_card, digital_wallet, or bank_transfer.",
            true,
          )}
          {renderField(
            "country",
            "Country",
            "2-letter country code such as US, GB, or RU. Used for geographic risk signals.",
            true,
          )}
          {renderField(
            "merchant_category",
            "Merchant Category",
            "Examples: groceries, restaurants, electronics, gaming, travel.",
            false,
          )}
          {renderField(
            "device_id",
            "Device ID",
            "Device identifier if available. Missing device context can become a risk signal.",
            false,
          )}
          {renderField("device_type", "Device Type", "Examples: desktop, mobile, tablet.", false)}

          {/* Is International checkbox */}
          <div className="block">
            <span className="mb-1 flex items-center">
              <span className="metric-label">Is International</span>
              <OptionalChip />
            </span>
            <label
              className="flex cursor-pointer items-center gap-2 rounded-md px-3 py-2"
              style={BASE_FIELD_STYLE}
            >
              <input
                type="checkbox"
                checked={fields.is_international}
                onChange={(event) =>
                  setFields((current) => ({
                    ...current,
                    is_international: event.target.checked,
                  }))
                }
                disabled={isSubmitting}
              />
              <span className="text-[13px]" style={{ color: "#C9D1D9" }}>
                Mark as cross-border transaction
              </span>
            </label>
            <p className="mt-1 text-[11px]" style={{ color: "#6B7280" }}>
              Marks cross-border or non-domestic transaction context.
            </p>
          </div>
        </div>
      </div>

      {/* Section B: Transaction Identity */}
      <div className="space-y-4" style={SECTION_STYLE}>
        <div>
          <p className="section-label">Transaction Identity</p>
          <p className="mt-1 text-[12px]" style={{ color: "#8B949E" }}>
            Required for case creation, routing, and audit traceability.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {renderField(
            "transaction_id",
            "Transaction ID",
            "Unique transaction reference. Auto-generated, but editable.",
            true,
          )}
          {renderField(
            "user_id",
            "User ID",
            "Customer or account identifier used for case traceability.",
            true,
          )}
          {renderField(
            "merchant_id",
            "Merchant ID",
            "Merchant, counterparty, or payee reference used for case traceability.",
            true,
          )}
          {renderField(
            "currency",
            "Currency",
            "3-letter currency code, for example USD or GBP.",
            true,
          )}
        </div>
      </div>

      {/* Section C: Investigation Context */}
      <div style={SECTION_STYLE}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="section-label">Investigation Context</p>
            <p className="mt-1 text-[12px]" style={{ color: "#8B949E" }}>
              {showInvestigation
                ? "Additional context can enrich downstream analyst investigation. These fields support review quality and future behavioral intelligence."
                : "Investigation Context is optional and can enrich downstream review."}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowInvestigation((current) => !current)}
            disabled={isSubmitting}
            className="shrink-0 text-[12px] font-medium disabled:opacity-45"
            style={{ color: "#8B949E" }}
          >
            {showInvestigation ? "Hide Investigation Context" : "Show Investigation Context"}
          </button>
        </div>

        {showInvestigation && (
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            {renderField("city", "City", "Optional location context for analyst review.", false)}
            {renderField(
              "ip_address",
              "IP Address",
              "Optional network context for analyst review.",
              false,
            )}
          </div>
        )}
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-md px-4 py-2.5 text-[13px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-45"
        style={{
          background: "rgba(34,211,238,0.10)",
          border: "1px solid rgba(34,211,238,0.28)",
          color: "#22D3EE",
        }}
      >
        {isSubmitting ? "Preparing Submission..." : "Submit for Risk Scoring"}
      </button>
    </form>
  );
}
