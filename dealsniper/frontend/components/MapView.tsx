"use client";

import { useMemo } from "react";
import { Map, MapControls } from "@/components/ui/map";
import {
  FlightRoutes,
  FlightAirport,
  type FlightRouteData,
} from "@/components/ui/flight";
import type { MapRoute, MapDeal } from "@/lib/api";

interface MapViewProps {
  routes: MapRoute[];
  deals: MapDeal[];
  onDealClick?: (dealId: number) => void;
}

export default function MapView({ routes, deals, onDealClick }: MapViewProps) {
  const routeData: FlightRouteData[] = useMemo(() => {
    return routes.map((r) => ({
      from: [r.origin_lng, r.origin_lat] as [number, number],
      to: [r.dest_lng, r.dest_lat] as [number, number],
      color: "#6366f1",
      width: 1.5,
      opacity: 0.3,
      lineStyle: "dash" as const,
    }));
  }, [routes]);

  const dealRouteData: FlightRouteData[] = useMemo(() => {
    return deals.map((d) => ({
      from: [d.origin_lng, d.origin_lat] as [number, number],
      to: [d.dest_lng, d.dest_lat] as [number, number],
      color: d.discount_pct >= 30 ? "#22c55e" : "#eab308",
      width: 2.5,
      opacity: 0.8,
    }));
  }, [deals]);

  const airports = useMemo(() => {
    const seen = new Set<string>();
    const result: { code: string; lng: number; lat: number }[] = [];
    const addAirport = (code: string, lng: number, lat: number) => {
      if (!seen.has(code)) {
        seen.add(code);
        result.push({ code, lng, lat });
      }
    };
    for (const d of deals) {
      addAirport(d.origin, d.origin_lng, d.origin_lat);
      addAirport(d.destination, d.dest_lng, d.dest_lat);
    }
    for (const r of routes) {
      addAirport(r.origin, r.origin_lng, r.origin_lat);
      addAirport(r.destination, r.dest_lng, r.dest_lat);
    }
    return result;
  }, [routes, deals]);

  return (
    <Map
      className="w-full h-full"
      viewport={{ center: [100, 10], zoom: 2.5 }}
      theme="dark"
    >
      <MapControls position="top-right" />

      {routeData.length > 0 && (
        <FlightRoutes routes={routeData} animate={{ duration: 8000 }} />
      )}

      {dealRouteData.length > 0 && (
        <FlightRoutes
          routes={dealRouteData}
          animate={{ duration: 3000 }}
          onClick={(index) => {
            const deal = deals[index];
            if (deal && onDealClick) onDealClick(deal.id);
          }}
        />
      )}

      {airports.map((ap) => (
        <FlightAirport
          key={ap.code}
          longitude={ap.lng}
          latitude={ap.lat}
          name={ap.code}
          showLabel
        />
      ))}
    </Map>
  );
}
