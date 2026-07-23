import { ApiError, type ApiErrorBody } from "@/lib/api/errors";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
const CSRF_COOKIE_NAME = "geniustrader_csrf";
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL
).replace(/\/$/, "");

interface ApiRequestOptions extends RequestInit {
  redirectOnUnauthorized?: boolean;
}

interface DataEnvelope<T> {
  data: T;
}

interface ErrorEnvelope {
  error: ApiErrorBody;
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers);

  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (UNSAFE_METHODS.has(method)) {
    const csrfToken = readCookie(CSRF_COOKIE_NAME);
    if (csrfToken && !headers.has("X-CSRF-Token")) {
      headers.set("X-CSRF-Token", csrfToken);
    }
  }

  const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    ...options,
    method,
    headers,
    credentials: "include"
  });

  const text = await response.text();
  const parsed = text ? safeJsonParse(text) : null;

  if (!response.ok) {
    const errorEnvelope = parsed as ErrorEnvelope | null;
    if (response.status === 401 && options.redirectOnUnauthorized !== false) {
      redirectToLogin();
    }
    if (errorEnvelope?.error) {
      throw new ApiError(errorEnvelope.error, response.status);
    }
    throw new ApiError(
      {
        code: "HTTP_ERROR",
        message: `请求失败：HTTP ${response.status}`,
        request_id: response.headers.get("X-Request-ID") ?? "unknown"
      },
      response.status
    );
  }

  if (!parsed) {
    return undefined as T;
  }

  return (parsed as DataEnvelope<T>).data;
}

export function toQueryString(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const value = search.toString();
  return value ? `?${value}` : "";
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const prefix = `${name}=`;
  const cookie = document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(prefix));
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
}

function redirectToLogin() {
  if (typeof window === "undefined" || window.location.pathname === "/login") {
    return;
  }

  const redirect = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
  window.location.assign(`/login?expired=1&redirect=${redirect}`);
}
