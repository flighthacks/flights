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

// ── Types ───────────────────────────────────────────────────────────────────

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
  min_observations: number;
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
  errors: number;
}

export interface ScanStatus {
  running: boolean;
  progress: number;
  current_route: string;
  routes_scanned: number;
  total_routes: number;
  observations_added: number;
  deals_found: number;
}

export interface MapRoute {
  origin: string;
  destination: string;
  origin_lat: number;
  origin_lng: number;
  dest_lat: number;
  dest_lng: number;
  cabin: string;
}

export interface MapDeal {
  id: number;
  origin: string;
  destination: string;
  origin_lat: number;
  origin_lng: number;
  dest_lat: number;
  dest_lng: number;
  price: number;
  avg_price: number;
  discount_pct: number;
  airline: string | null;
  cabin: string;
  outbound_date: string | null;
  return_date: string | null;
  booking_url: string | null;
  found_at: string;
}

export interface MapAirport {
  iata: string;
  lat: number;
  lng: number;
}

// ── API ─────────────────────────────────────────────────────────────────────

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
  }) =>
    fetchApi<MonitoredRoute>("/api/routes", {
      method: "POST",
      body: JSON.stringify(data),
    }),
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
  triggerScanAsync: () =>
    fetchApi<{ status: string }>("/api/scan/async", { method: "POST" }),
  getScanStatus: () => fetchApi<ScanStatus>("/api/scan/status"),

  getMapRoutes: () => fetchApi<MapRoute[]>("/api/map/routes"),
  getMapDeals: () => fetchApi<MapDeal[]>("/api/map/deals"),
  getMapAirports: () => fetchApi<MapAirport[]>("/api/map/airports"),
};
