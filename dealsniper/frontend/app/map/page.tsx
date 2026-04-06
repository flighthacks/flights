"use client";

import { useEffect, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { api, MapDeal, MapRoute } from "@/lib/api";
import DealDrawer from "@/components/DealDrawer";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

export default function MapPage() {
  const [routes, setRoutes] = useState<MapRoute[]>([]);
  const [deals, setDeals] = useState<MapDeal[]>([]);
  const [selectedDeal, setSelectedDeal] = useState<MapDeal | null>(null);

  useEffect(() => {
    api.getMapRoutes().then(setRoutes).catch(console.error);
    api.getMapDeals().then(setDeals).catch(console.error);
  }, []);

  const handleDealClick = useCallback(
    (dealId: number) => {
      const deal = deals.find((d) => d.id === dealId);
      setSelectedDeal(deal || null);
    },
    [deals]
  );

  return (
    <div className="relative -m-6 h-[calc(100vh-0px)]">
      <MapView
        routes={routes}
        deals={deals}
        onDealClick={handleDealClick}
      />
      <DealDrawer deal={selectedDeal} onClose={() => setSelectedDeal(null)} />
    </div>
  );
}
