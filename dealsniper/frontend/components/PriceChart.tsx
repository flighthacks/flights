"use client";

import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Area,
  AreaChart,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, PricePoint } from "@/lib/api";

interface PriceChartProps {
  origin: string;
  destination: string;
  cabin?: string;
  days?: number;
}

export default function PriceChart({
  origin,
  destination,
  cabin = "economy",
  days = 30,
}: PriceChartProps) {
  const [data, setData] = useState<PricePoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .getPriceChart(origin, destination, cabin, days)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [origin, destination, cabin, days]);

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="h-64 animate-pulse bg-muted rounded" />
        </CardContent>
      </Card>
    );
  }

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">
            {origin} → {destination} ({cabin})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-sm">
            No price data yet. Run a scan to start collecting prices.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">
          {origin} → {destination} — {cabin} (last {days}d)
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
            <Tooltip
              formatter={(value) => [`$${value}`, ""]}
              labelFormatter={(label) => `Date: ${label}`}
            />
            <Legend />
            <Area
              type="monotone"
              dataKey="max_price"
              stroke="#f87171"
              fill="#fecaca"
              fillOpacity={0.3}
              name="Max"
            />
            <Area
              type="monotone"
              dataKey="avg_price"
              stroke="#3b82f6"
              fill="#93c5fd"
              fillOpacity={0.4}
              name="Average"
            />
            <Area
              type="monotone"
              dataKey="min_price"
              stroke="#22c55e"
              fill="#bbf7d0"
              fillOpacity={0.3}
              name="Min"
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
