// Browser-side API client. Every call goes to /api/* on this origin; the Next route handler in
// src/app/api/[...path]/route.ts forwards it to the FastAPI backend.

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public retryAfter?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Detail = string | { msg?: string; loc?: (string | number)[] }[] | undefined;

function describe(detail: Detail, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d) => {
        const field = d.loc?.filter((p) => p !== "body").join(".");
        const msg = (d.msg ?? "is invalid").replace(/^Value error, /, "");
        return field ? `${field}: ${msg}` : msg;
      })
      .join("; ");
  }
  if (status === 429) return "Too many requests. Please wait a moment and try again.";
  if (status >= 500) return "The server had a problem. Please try again.";
  return `Request failed (${status})`;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { ...init, headers, credentials: "same-origin", cache: "no-store" });
  } catch {
    throw new ApiError(0, "Network error: check your connection and try again.");
  }
  if (res.status === 204) return undefined as T;
  let body: { detail?: Detail } | undefined;
  try {
    body = await res.json();
  } catch {
    body = undefined;
  }
  if (!res.ok) {
    const retry = Number(res.headers.get("retry-after")) || undefined;
    throw new ApiError(res.status, describe(body?.detail, res.status), retry);
  }
  return body as T;
}

export const json = (data: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(data) });
