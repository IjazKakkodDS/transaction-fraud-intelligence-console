import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatUSD(amount: number | null): string {
  if (amount === null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatRiskScore(score: number | null): string {
  if (score === null) return "—";
  if (score >= 0 && score <= 1) return `${(score * 100).toFixed(1)}%`;
  return score.toFixed(3);
}

export function formatDateShort(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateFull(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatLabel(raw: string | null | undefined): string {
  if (!raw) return "";
  return raw
    .toLowerCase()
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function sanitizeWorkflowMessage(msg: string): string {
  return msg
    .replace(/\bn8n\s+webhook\b/gi, "Automation endpoint")
    .replace(/\bnon-2xx\s+response\b/gi, "non-success response")
    .replace(/\bn8n\b/gi, "Automation")
    .replace(/\bFastAPI\b/gi, "API");
}
