"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { listSearches, listAlerts, deleteAlert, getSearchResult } from "@/lib/api";

interface SearchJob {
  job_id: string;
  status: string;
  created_at: string;
  query: string;
}

interface Alert {
  id: string;
  query: string;
  target_price: number;
  cabin: string;
  last_price: number | null;
  created_at: string;
}

export default function DashboardPage() {
  const [searches, setSearches] = useState<SearchJob[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [s, a] = await Promise.all([listSearches(), listAlerts()]);
        setSearches(s);
        setAlerts(a);
      } catch {
        // Not logged in — redirect
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleDeleteAlert(id: string) {
    await deleteAlert(id);
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="border-b bg-white">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold text-brand-700">
            Autofare
          </Link>
          <div className="flex items-center gap-4">
            <Link
              href="/search"
              className="bg-brand-600 text-white px-4 py-1.5 rounded-lg text-sm hover:bg-brand-700"
            >
              New Search
            </Link>
            <Link href="/billing" className="text-gray-600 hover:text-gray-900 text-sm">
              Billing
            </Link>
          </div>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

        {/* Recent searches */}
        <div className="bg-white rounded-xl shadow border mb-8">
          <div className="px-6 py-4 border-b flex items-center justify-between">
            <h2 className="font-semibold">Recent Searches</h2>
            <Link href="/search" className="text-brand-600 text-sm hover:underline">
              New search
            </Link>
          </div>

          {searches.length === 0 ? (
            <div className="px-6 py-12 text-center text-gray-500">
              <p className="mb-4">No searches yet</p>
              <Link
                href="/search"
                className="bg-brand-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-brand-700"
              >
                Run your first search
              </Link>
            </div>
          ) : (
            <div className="divide-y">
              {searches.map((s) => (
                <Link
                  key={s.job_id}
                  href={`/search?job=${s.job_id}`}
                  className="block px-6 py-4 hover:bg-gray-50 transition"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">{s.query}</div>
                      <div className="text-sm text-gray-500">
                        {new Date(s.created_at).toLocaleDateString()} at{" "}
                        {new Date(s.created_at).toLocaleTimeString()}
                      </div>
                    </div>
                    <StatusBadge status={s.status} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Price alerts */}
        <div className="bg-white rounded-xl shadow border">
          <div className="px-6 py-4 border-b">
            <h2 className="font-semibold">Price Alerts</h2>
          </div>

          {alerts.length === 0 ? (
            <div className="px-6 py-12 text-center text-gray-500">
              <p>No price alerts set up</p>
              <p className="text-sm mt-1">
                Run a search and set an alert to be notified when the price drops.
              </p>
            </div>
          ) : (
            <div className="divide-y">
              {alerts.map((a) => (
                <div
                  key={a.id}
                  className="px-6 py-4 flex items-center justify-between"
                >
                  <div>
                    <div className="font-medium">{a.query}</div>
                    <div className="text-sm text-gray-500">
                      Alert when below ${a.target_price.toLocaleString()} ({a.cabin})
                      {a.last_price && (
                        <span className="ml-2">
                          Last: ${a.last_price.toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteAlert(a.id)}
                    className="text-red-500 hover:text-red-700 text-sm"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    running: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
  };
  return (
    <span
      className={`text-xs px-2 py-1 rounded-full ${styles[status] || "bg-gray-100 text-gray-600"}`}
    >
      {status}
    </span>
  );
}
