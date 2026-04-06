"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { api, Stats } from "@/lib/api";

export default function StatsBar() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    api.getStats().then(setStats).catch(console.error);
  }, []);

  if (!stats) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardContent className="p-4">
              <div className="h-12 animate-pulse bg-muted rounded" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const items = [
    { label: "Active Deals", value: stats.total_deals, color: "text-green-500" },
    { label: "Price Points", value: stats.total_observations.toLocaleString(), color: "text-blue-500" },
    { label: "Monitored Routes", value: stats.active_routes, color: "text-purple-500" },
    {
      label: "Avg Discount",
      value: stats.avg_discount ? `${stats.avg_discount}%` : "—",
      color: "text-orange-500",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {items.map((item, i) => (
        <motion.div
          key={item.label}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.1 }}
        >
          <Card>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">{item.label}</p>
              <p className={`text-2xl font-bold ${item.color}`}>{item.value}</p>
            </CardContent>
          </Card>
        </motion.div>
      ))}
    </div>
  );
}
