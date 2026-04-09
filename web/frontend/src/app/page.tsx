"use client";

import { useState } from "react";
import Link from "next/link";

export default function LandingPage() {
  return (
    <div className="min-h-screen">
      {/* Nav */}
      <nav className="border-b bg-white">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-2xl font-bold text-brand-700">Autofare</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/login" className="text-gray-600 hover:text-gray-900">
              Log in
            </Link>
            <Link
              href="/register"
              className="bg-brand-600 text-white px-4 py-2 rounded-lg hover:bg-brand-700 transition"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-4 py-20 text-center">
        <h1 className="text-5xl font-bold tracking-tight mb-6">
          Find the cheapest
          <span className="text-brand-600"> business class </span>
          flights
        </h1>
        <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-10">
          Our AI searches hundreds of route combinations — alternate airports,
          date shifts, hub routing, split tickets — to find fares most people
          miss.
        </p>
        <Link
          href="/register"
          className="inline-block bg-brand-600 text-white text-lg px-8 py-4 rounded-lg hover:bg-brand-700 transition shadow-lg"
        >
          Start Searching for Free
        </Link>
        <p className="mt-4 text-sm text-gray-500">
          2 free searches per month. No credit card required.
        </p>
      </section>

      {/* How it works */}
      <section className="bg-white border-t border-b py-20">
        <div className="max-w-6xl mx-auto px-4">
          <h2 className="text-3xl font-bold text-center mb-12">How it works</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <Step
              num="1"
              title="Describe your trip"
              desc='Type naturally: "Business class London to Tokyo, late July, 4 weeks"'
            />
            <Step
              num="2"
              title="AI explores every angle"
              desc="We search 200+ route variations — alternate airports, dates, hubs, split tickets — in minutes."
            />
            <Step
              num="3"
              title="Get the best fare"
              desc="See ranked results with savings vs. the obvious booking. Typical savings: 20-40%."
            />
          </div>
        </div>
      </section>

      {/* Example result */}
      <section className="max-w-6xl mx-auto px-4 py-20">
        <h2 className="text-3xl font-bold text-center mb-4">Real results</h2>
        <p className="text-center text-gray-600 mb-10">
          From an actual Autofare search: Europe to Seoul, business class
        </p>
        <div className="max-w-2xl mx-auto bg-white rounded-xl shadow-lg border p-8">
          <div className="flex justify-between items-start mb-6">
            <div>
              <div className="text-sm text-gray-500">Baseline (direct booking)</div>
              <div className="text-2xl font-bold text-gray-400 line-through">
                $2,372
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm text-green-600 font-medium">
                Autofare found
              </div>
              <div className="text-3xl font-bold text-green-600">$1,715</div>
            </div>
          </div>
          <div className="border-t pt-4">
            <div className="text-lg font-medium">IST → ICN</div>
            <div className="text-gray-600">
              Turkish Airlines + Finnair · 1 stop · 21h 50m
            </div>
            <div className="mt-2 inline-block bg-green-100 text-green-800 text-sm px-3 py-1 rounded-full">
              Save $657 (27.7%)
            </div>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="bg-white border-t py-20">
        <div className="max-w-6xl mx-auto px-4">
          <h2 className="text-3xl font-bold text-center mb-12">
            Simple pricing
          </h2>
          <div className="grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
            <PricingCard
              tier="Free"
              price="$0"
              features={[
                "2 searches / month",
                "Top 5 results",
                "Basic route optimization",
              ]}
              cta="Get Started"
              href="/register"
            />
            <PricingCard
              tier="Pro"
              price="$29"
              period="/mo"
              features={[
                "Unlimited searches",
                "All results + details",
                "Price alerts (10)",
                "Search history",
                "Priority support",
              ]}
              cta="Start Pro Trial"
              href="/register"
              highlighted
            />
            <PricingCard
              tier="Business"
              price="$79"
              period="/mo"
              features={[
                "Everything in Pro",
                "API access",
                "Team sharing",
                "CSV export",
                "50 price alerts",
                "Dedicated support",
              ]}
              cta="Contact Sales"
              href="/register"
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-8 text-center text-gray-500 text-sm">
        <p>Autofare — AI-powered flight search optimization</p>
      </footer>
    </div>
  );
}

function Step({
  num,
  title,
  desc,
}: {
  num: string;
  title: string;
  desc: string;
}) {
  return (
    <div className="text-center">
      <div className="w-12 h-12 rounded-full bg-brand-100 text-brand-700 font-bold text-xl flex items-center justify-center mx-auto mb-4">
        {num}
      </div>
      <h3 className="text-lg font-semibold mb-2">{title}</h3>
      <p className="text-gray-600">{desc}</p>
    </div>
  );
}

function PricingCard({
  tier,
  price,
  period,
  features,
  cta,
  href,
  highlighted,
}: {
  tier: string;
  price: string;
  period?: string;
  features: string[];
  cta: string;
  href: string;
  highlighted?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-6 ${
        highlighted
          ? "border-brand-500 shadow-lg ring-2 ring-brand-200"
          : "border-gray-200"
      }`}
    >
      <h3 className="text-lg font-semibold mb-2">{tier}</h3>
      <div className="mb-6">
        <span className="text-4xl font-bold">{price}</span>
        {period && <span className="text-gray-500">{period}</span>}
      </div>
      <ul className="space-y-2 mb-8">
        {features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm">
            <span className="text-green-500 mt-0.5">&#10003;</span>
            {f}
          </li>
        ))}
      </ul>
      <Link
        href={href}
        className={`block text-center py-2 rounded-lg transition ${
          highlighted
            ? "bg-brand-600 text-white hover:bg-brand-700"
            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
        }`}
      >
        {cta}
      </Link>
    </div>
  );
}
