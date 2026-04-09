"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { getBillingStatus, createCheckout } from "@/lib/api";

interface BillingInfo {
  tier: string;
  searches_used: number;
  searches_limit: number;
  alerts_limit: number;
  max_results: number;
}

export default function BillingPage() {
  const [billing, setBilling] = useState<BillingInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getBillingStatus()
      .then(setBilling)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleUpgrade(tier: string) {
    try {
      const { checkout_url } = await createCheckout(tier);
      window.location.href = checkout_url;
    } catch (err: any) {
      alert(err.message || "Failed to create checkout session");
    }
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
            <Link href="/search" className="text-gray-600 hover:text-gray-900 text-sm">
              Search
            </Link>
            <Link href="/dashboard" className="text-gray-600 hover:text-gray-900 text-sm">
              Dashboard
            </Link>
          </div>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-6">Billing</h1>

        {/* Current plan */}
        {billing && (
          <div className="bg-white rounded-xl shadow border p-6 mb-8">
            <h2 className="text-lg font-semibold mb-4">Current Plan</h2>
            <div className="flex items-center gap-4 mb-4">
              <span className="text-2xl font-bold capitalize">{billing.tier}</span>
              {billing.tier === "free" && (
                <span className="text-sm text-gray-500">Free plan</span>
              )}
            </div>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="text-gray-500">Searches this month</div>
                <div className="text-xl font-bold">
                  {billing.searches_used} / {billing.searches_limit === 999 ? "\u221e" : billing.searches_limit}
                </div>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="text-gray-500">Results per search</div>
                <div className="text-xl font-bold">
                  {billing.max_results === 999 ? "All" : `Top ${billing.max_results}`}
                </div>
              </div>
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="text-gray-500">Price alerts</div>
                <div className="text-xl font-bold">
                  {billing.alerts_limit === 0 ? "None" : billing.alerts_limit}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Plans */}
        <div className="grid md:grid-cols-3 gap-6">
          <PlanCard
            name="Free"
            price="$0"
            current={billing?.tier === "free"}
            features={["2 searches / month", "Top 5 results", "Basic optimization"]}
          />
          <PlanCard
            name="Pro"
            price="$29/mo"
            current={billing?.tier === "pro"}
            highlighted
            features={[
              "Unlimited searches",
              "All results",
              "10 price alerts",
              "Full search history",
              "Priority support",
            ]}
            onUpgrade={() => handleUpgrade("pro")}
          />
          <PlanCard
            name="Business"
            price="$79/mo"
            current={billing?.tier === "business"}
            features={[
              "Everything in Pro",
              "API access",
              "Team sharing",
              "CSV export",
              "50 price alerts",
              "Dedicated support",
            ]}
            onUpgrade={() => handleUpgrade("business")}
          />
        </div>
      </div>
    </div>
  );
}

function PlanCard({
  name,
  price,
  current,
  highlighted,
  features,
  onUpgrade,
}: {
  name: string;
  price: string;
  current?: boolean;
  highlighted?: boolean;
  features: string[];
  onUpgrade?: () => void;
}) {
  return (
    <div
      className={`rounded-xl border p-6 ${
        highlighted ? "border-brand-500 ring-2 ring-brand-200" : "border-gray-200"
      }`}
    >
      <h3 className="text-lg font-semibold">{name}</h3>
      <div className="text-3xl font-bold my-3">{price}</div>

      <ul className="space-y-2 mb-6">
        {features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm">
            <span className="text-green-500 mt-0.5">&#10003;</span>
            {f}
          </li>
        ))}
      </ul>

      {current ? (
        <div className="text-center py-2 bg-gray-100 rounded-lg text-gray-600 text-sm">
          Current plan
        </div>
      ) : onUpgrade ? (
        <button
          onClick={onUpgrade}
          className={`w-full py-2 rounded-lg transition text-sm ${
            highlighted
              ? "bg-brand-600 text-white hover:bg-brand-700"
              : "bg-gray-100 text-gray-700 hover:bg-gray-200"
          }`}
        >
          Upgrade
        </button>
      ) : null}
    </div>
  );
}
