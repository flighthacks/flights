"use client";

import { useEffect, useState, useCallback } from "react";
import StatsBar from "@/components/StatsBar";
import DealCard from "@/components/DealCard";
import PriceChart from "@/components/PriceChart";
import ScanProgress from "@/components/ScanProgress";
import { api, Deal, MonitoredRoute } from "@/lib/api";

export default function Dashboard() {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [routes, setRoutes] = useState<MonitoredRoute[]>([]);

  const loadDeals = useCallback(() => {
    api.getDeals().then(setDeals).catch(console.error);
  }, []);

  useEffect(() => {
    loadDeals();
    api.getRoutes().then(setRoutes).catch(console.error);
  }, [loadDeals]);

  const activeRoutes = routes.filter((r) => r.active);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <ScanProgress onComplete={loadDeals} />
      </div>

      <StatsBar />

      {deals.length > 0 ? (
        <section>
          <h2 className="text-lg font-semibold mb-3">Latest Deals</h2>
          <div className="space-y-3">
            {deals.map((deal) => (
              <DealCard key={deal.id} deal={deal} onDismiss={loadDeals} />
            ))}
          </div>
        </section>
      ) : (
        <div className="text-center py-16 text-muted-foreground">
          <p className="text-lg">No deals found yet</p>
          <p className="text-sm mt-1">
            Add some routes and run a scan, or wait for the scheduled scanner
          </p>
        </div>
      )}

      {activeRoutes.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold mb-3">Price History</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {activeRoutes
              .filter((r) => r.destination !== "ANYWHERE")
              .slice(0, 4)
              .map((route) => (
                <PriceChart
                  key={route.id}
                  origin={route.origin}
                  destination={route.destination}
                  cabin={route.cabin}
                />
              ))}
          </div>
        </section>
      )}
    </div>
  );
}
