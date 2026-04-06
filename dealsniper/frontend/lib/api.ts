const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// Types
export interface Stats {
  total_observations: number;
  total_deals: number;
  active_routes: number;
  avg_discount: number | null;
}

export interface Deal {
  id: number;
  origin: string;
  destination: string;
  cabin: string;
  trip_type: string;
  price: number;
  avg_price: number;
  discount_pct: number;
  airline: string | null;
  outbound_date: string | null;
  return_date: string | null;
  booking_url: string | null;
  found_at: string;
  is_dismissed: boolean;
}

export interface MonitoredRoute {
  id: number;
  origin: string;
  destination: string;
  cabin: string;
  trip_type: string;
  active: boolean;
  created_at: string;
}

export interface Settings {
  origins: string[];
  deal_threshold: number;
  scan_interval_hours: number;
  lookahead_days: number;
  min_observations_before_alert: number;
}

export interface PricePoint {
  date: string;
  avg_price: number;
  min_price: number;
  max_price: number;
  count: number;
}

export interface ScanResult {
  routes_scanned: number;
  observations_added: number;
  deals_found: number;
}

// API functions
export const api = {
  getStats: () => fetchApi<Stats>("/api/stats"),
  getDeals: (includeDismissed = false) =>
    fetchApi<Deal[]>(`/api/deals?include_dismissed=${includeDismissed}`),
  dismissDeal: (id: number) =>
    fetchApi<{ status: string }>(`/api/deals/${id}/dismiss`, { method: "POST" }),

  getRoutes: () => fetchApi<MonitoredRoute[]>("/api/routes"),
  createRoute: (data: {
    origin: string;
    destination: string;
    cabin: string;
    trip_type: string;
  }) => fetchApi<MonitoredRoute>("/api/routes", { method: "POST", body: JSON.stringify(data) }),
  deleteRoute: (id: number) =>
    fetchApi<{ status: string }>(`/api/routes/${id}`, { method: "DELETE" }),
  toggleRoute: (id: number) =>
    fetchApi<{ status: string; active: boolean }>(`/api/routes/${id}/toggle`, {
      method: "PATCH",
    }),

  getPriceChart: (origin: string, destination: string, cabin = "economy", days = 30) =>
    fetchApi<PricePoint[]>(
      `/api/prices/chart?origin=${origin}&destination=${destination}&cabin=${cabin}&days=${days}`
    ),

  getSettings: () => fetchApi<Settings>("/api/settings"),
  updateSettings: (data: Partial<Settings>) =>
    fetchApi<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(data) }),

  triggerScan: () => fetchApi<ScanResult>("/api/scan", { method: "POST" }),
};
