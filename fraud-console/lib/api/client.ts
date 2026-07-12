import { z } from "zod";
import { ApiError } from "@/types/api";

const BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

// ---------------------------------------------------------------------------
// Options type — extends RequestInit with an optional Zod schema.
// When schema is provided, the parsed+validated value is returned as T.
// When omitted, the raw JSON is cast to T without runtime validation.
// ---------------------------------------------------------------------------

export interface ApiFetchOptions<T> extends Omit<RequestInit, "body"> {
  schema?: z.ZodType<T>;
  body?: unknown;
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

export async function apiFetch<T = unknown>(
  path: string,
  options?: ApiFetchOptions<T>,
): Promise<T> {
  const { schema, body, headers: customHeaders, ...rest } = options ?? {};

  const url = path.startsWith("http") ? path : `${BASE_URL}${path}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(customHeaders as Record<string, string> | undefined),
  };

  const response = await fetch(url, {
    ...rest,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // Non-2xx — extract FastAPI detail string if available, then throw.
  if (!response.ok) {
    let detail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const json = await response.json();
      if (typeof json?.detail === "string") detail = json.detail;
    } catch {
      // Response body was not JSON — keep the default message.
    }
    throw new ApiError(response.status, detail);
  }

  // 204 No Content — nothing to parse.
  if (response.status === 204) {
    return undefined as T;
  }

  const data: unknown = await response.json();

  // Validate at the boundary when a schema is provided.
  if (schema) {
    return schema.parse(data);
  }

  return data as T;
}
