/**
 * API client for the Autofare backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("autofare_token");
}

async function apiFetch(path: string, options: RequestInit = {}): Promise<any> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }
  return res.json();
}

// ---- Auth ----

export async function register(email: string, password: string, name: string) {
  const data = await apiFetch("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, name }),
  });
  localStorage.setItem("autofare_token", data.access_token);
  return data;
}

export async function login(email: string, password: string) {
  const data = await apiFetch("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem("autofare_token", data.access_token);
  return data;
}

export function logout() {
  localStorage.removeItem("autofare_token");
}

export async function getMe() {
  return apiFetch("/api/auth/me");
}

// ---- Search ----

export async function createSearch(params: {
  query: string;
  config_yaml?: string;
  cabin?: string;
  flex_days?: number;
  max_searches?: number;
  currency?: string;
}) {
  return apiFetch("/api/search", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function getSearchResult(jobId: string) {
  return apiFetch(`/api/search/${jobId}`);
}

export async function listSearches(limit = 20, offset = 0) {
  return apiFetch(`/api/searches?limit=${limit}&offset=${offset}`);
}

export function streamSearchProgress(
  jobId: string,
  onProgress: (data: any) => void,
  onDone: () => void
): () => void {
  const token = getToken();
  const url = `${API_BASE}/api/search/${jobId}/stream`;

  const eventSource = new EventSource(url);
  // Note: EventSource doesn't support custom headers.
  // For auth with SSE, use query params or cookies in production.

  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onProgress(data);
    if (data.final) {
      eventSource.close();
      onDone();
    }
  };

  eventSource.onerror = () => {
    eventSource.close();
    onDone();
  };

  return () => eventSource.close();
}

// ---- Alerts ----

export async function createAlert(params: {
  query: string;
  target_price: number;
  cabin?: string;
  currency?: string;
}) {
  return apiFetch("/api/alerts", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function listAlerts() {
  return apiFetch("/api/alerts");
}

export async function deleteAlert(alertId: string) {
  return apiFetch(`/api/alerts/${alertId}`, { method: "DELETE" });
}

// ---- Billing ----

export async function createCheckout(tier: string) {
  return apiFetch(`/api/billing/checkout?tier=${tier}`, { method: "POST" });
}

export async function getBillingStatus() {
  return apiFetch("/api/billing/status");
}

export function isLoggedIn(): boolean {
  return !!getToken();
}
