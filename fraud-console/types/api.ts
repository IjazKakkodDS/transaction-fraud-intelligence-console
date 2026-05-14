/**
 * Shared API primitives used across all domain type modules.
 * ApiError is thrown by apiFetch on any non-2xx response.
 */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}
