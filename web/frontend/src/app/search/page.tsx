"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { createSearch, getSearchResult, streamSearchProgress } from "@/lib/api";

interface SearchProgress {
  status: string;
  message?: string;
  phase?: string;
  searches_done?: number;
  searches_total?: number;
  best_price?: number;
  baseline_price?: number;
  strategy?: string;
  new_best?: boolean;
  iteration?: number;
  final?: boolean;
}

interface FlightResult {
  origin: string;
  destination: string;
  date: string;
  airline: string;
  price: number;
  stops: number;
  duration: string;
  departure_time: string;
  arrival_time: string;
  strategy: string;
}

interface SearchResultData {
  job_id: string;
  status: string;
  baseline_price: number | null;
  best_price: number | null;
  savings: number | null;
  savings_pct: number | null;
  best_route: string | null;
  best_airline: string | null;
  total_searches: number;
  top_results: FlightResult[];
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [cabin, setCabin] = useState("business");
  const [flexDays, setFlexDays] = useState(2);
  const [maxSearches, setMaxSearches] = useState(100);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<SearchProgress | null>(null);
  const [result, setResult] = useState<SearchResultData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Poll for final results when search completes
  const fetchResult = useCallback(async (id: string) => {
    try {
      const data = await getSearchResult(id);
      setResult(data);
    } catch (err: any) {
      setError(err.message);
    }
  }, []);

  // Start SSE stream when job starts
  useEffect(() => {
    if (!jobId) return;

    const close = streamSearchProgress(
      jobId,
      (data: SearchProgress) => {
        setProgress(data);
      },
      () => {
        // SSE done — fetch final result
        fetchResult(jobId);
      }
    );

    return close;
  }, [jobId, fetchResult]);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    setError("");
    setLoading(true);
    setProgress(null);
    setResult(null);

    try {
      const job = await createSearch({
        query: query.trim(),
        cabin,
        flex_days: flexDays,
        max_searches: maxSearches,
      });
      setJobId(job.job_id);
    } catch (err: any) {
      setError(err.message || "Failed to start search");
    } finally {
      setLoading(false);
    }
  }

  const isSearching = progress && !progress.final && progress.status !== "completed" && progress.status !== "failed";
  const pct = progress?.searches_done && progress?.searches_total
    ? Math.round((progress.searches_done / progress.searches_total) * 100)
    : 0;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Nav */}
      <nav className="border-b bg-white">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold text-brand-700">
            Autofare
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-gray-600 hover:text-gray-900 text-sm">
              Dashboard
            </Link>
            <Link href="/billing" className="text-gray-600 hover:text-gray-900 text-sm">
              Billing
            </Link>
          </div>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Search form */}
        <form onSubmit={handleSearch} className="bg-white rounded-xl shadow-lg border p-6 mb-8">
          <h1 className="text-2xl font-bold mb-4">Search for flights</h1>

          <div className="mb-4">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder='e.g., "Business class London to Tokyo, late July, return end of August"'
              className="w-full rounded-lg border border-gray-300 px-4 py-3 text-lg focus:border-brand-500 focus:ring-brand-500 resize-none"
              rows={2}
            />
          </div>

          <div className="flex items-center gap-4 mb-4">
            <select
              value={cabin}
              onChange={(e) => setCabin(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="economy">Economy</option>
              <option value="premium-economy">Premium Economy</option>
              <option value="business">Business</option>
              <option value="first">First</option>
            </select>

            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              {showAdvanced ? "Hide" : "Show"} advanced options
            </button>
          </div>

          {showAdvanced && (
            <div className="grid grid-cols-2 gap-4 mb-4 p-4 bg-gray-50 rounded-lg">
              <label className="block">
                <span className="text-sm text-gray-600">Date flexibility</span>
                <select
                  value={flexDays}
                  onChange={(e) => setFlexDays(Number(e.target.value))}
                  className="mt-1 block w-full rounded border border-gray-300 px-2 py-1 text-sm"
                >
                  <option value={0}>Exact dates</option>
                  <option value={1}>+/- 1 day</option>
                  <option value={2}>+/- 2 days</option>
                  <option value={3}>+/- 3 days</option>
                  <option value={5}>+/- 5 days</option>
                </select>
              </label>
              <label className="block">
                <span className="text-sm text-gray-600">Search budget</span>
                <select
                  value={maxSearches}
                  onChange={(e) => setMaxSearches(Number(e.target.value))}
                  className="mt-1 block w-full rounded border border-gray-300 px-2 py-1 text-sm"
                >
                  <option value={50}>Quick (50 searches)</option>
                  <option value={100}>Standard (100 searches)</option>
                  <option value={200}>Thorough (200 searches)</option>
                  <option value={300}>Maximum (300 searches)</option>
                </select>
              </label>
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !!isSearching}
            className="w-full bg-brand-600 text-white py-3 rounded-lg text-lg font-medium hover:bg-brand-700 transition disabled:opacity-50"
          >
            {isSearching ? "Searching..." : "Find Cheapest Flights"}
          </button>

          {error && (
            <div className="mt-4 bg-red-50 text-red-700 p-3 rounded-lg text-sm">
              {error}
            </div>
          )}
        </form>

        {/* Live progress */}
        {isSearching && progress && (
          <div className="bg-white rounded-xl shadow border p-6 mb-8">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-brand-500 animate-pulse-glow" />
                <span className="font-medium">
                  {progress.phase === "baseline" ? "Searching baseline routes..." : "Optimizing..."}
                </span>
              </div>
              <span className="text-sm text-gray-500">
                {progress.searches_done} / {progress.searches_total} searches
              </span>
            </div>

            {/* Progress bar */}
            <div className="w-full bg-gray-200 rounded-full h-2 mb-3">
              <div
                className="bg-brand-500 h-2 rounded-full transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>

            <div className="text-sm text-gray-600">{progress.message}</div>

            {progress.best_price && (
              <div className="mt-3 flex items-center gap-4">
                {progress.baseline_price && (
                  <span className="text-gray-400 line-through">
                    ${progress.baseline_price.toLocaleString()}
                  </span>
                )}
                <span className="text-xl font-bold text-green-600">
                  ${progress.best_price.toLocaleString()}
                </span>
                {progress.new_best && (
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                    New best!
                  </span>
                )}
              </div>
            )}
          </div>
        )}

        {/* Results */}
        {result && result.status === "completed" && (
          <div>
            {/* Summary card */}
            <div className="bg-white rounded-xl shadow border p-6 mb-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold">Search Complete</h2>
                <span className="text-sm text-gray-500">
                  {result.total_searches} searches executed
                </span>
              </div>

              {result.savings && result.savings > 0 ? (
                <div className="flex items-center gap-6">
                  <div>
                    <div className="text-sm text-gray-500">Baseline</div>
                    <div className="text-xl text-gray-400 line-through">
                      ${result.baseline_price?.toLocaleString()}
                    </div>
                  </div>
                  <div className="text-3xl text-gray-300">&rarr;</div>
                  <div>
                    <div className="text-sm text-green-600 font-medium">Best found</div>
                    <div className="text-3xl font-bold text-green-600">
                      ${result.best_price?.toLocaleString()}
                    </div>
                  </div>
                  <div className="ml-auto">
                    <div className="bg-green-100 text-green-800 px-4 py-2 rounded-lg text-center">
                      <div className="text-2xl font-bold">
                        ${result.savings.toLocaleString()}
                      </div>
                      <div className="text-sm">saved ({result.savings_pct?.toFixed(1)}%)</div>
                    </div>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="text-sm text-gray-500">Best price found</div>
                  <div className="text-3xl font-bold">
                    ${result.best_price?.toLocaleString() || "N/A"}
                  </div>
                </div>
              )}

              {result.best_route && (
                <div className="mt-4 text-gray-600">
                  Best route: <strong>{result.best_route}</strong>
                  {result.best_airline && ` on ${result.best_airline}`}
                </div>
              )}
            </div>

            {/* Results table */}
            {result.top_results.length > 0 && (
              <div className="bg-white rounded-xl shadow border overflow-hidden">
                <div className="px-6 py-4 border-b">
                  <h3 className="font-semibold">All results</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-left">
                      <tr>
                        <th className="px-4 py-3 font-medium">#</th>
                        <th className="px-4 py-3 font-medium">Route</th>
                        <th className="px-4 py-3 font-medium">Date</th>
                        <th className="px-4 py-3 font-medium">Airline</th>
                        <th className="px-4 py-3 font-medium">Price</th>
                        <th className="px-4 py-3 font-medium">Stops</th>
                        <th className="px-4 py-3 font-medium">Duration</th>
                        <th className="px-4 py-3 font-medium">Strategy</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.top_results.map((r, i) => (
                        <tr
                          key={i}
                          className={`border-t ${i === 0 ? "bg-green-50" : "hover:bg-gray-50"}`}
                        >
                          <td className="px-4 py-3 text-gray-500">{i + 1}</td>
                          <td className="px-4 py-3 font-medium">
                            {r.origin} &rarr; {r.destination}
                          </td>
                          <td className="px-4 py-3">{r.date}</td>
                          <td className="px-4 py-3">{r.airline || "—"}</td>
                          <td className="px-4 py-3 font-semibold">
                            ${r.price.toLocaleString()}
                          </td>
                          <td className="px-4 py-3">
                            {r.stops >= 0 ? r.stops : "—"}
                          </td>
                          <td className="px-4 py-3">{r.duration || "—"}</td>
                          <td className="px-4 py-3">
                            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                              {r.strategy}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
