"use client";

import { motion } from "framer-motion";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Deal, api } from "@/lib/api";

const cabinColors: Record<string, string> = {
  economy: "bg-blue-100 text-blue-800",
  premium_economy: "bg-purple-100 text-purple-800",
  business: "bg-amber-100 text-amber-800",
  first: "bg-red-100 text-red-800",
};

interface DealCardProps {
  deal: Deal;
  onDismiss?: () => void;
}

export default function DealCard({ deal, onDismiss }: DealCardProps) {
  const handleDismiss = async () => {
    await api.dismissDeal(deal.id);
    onDismiss?.();
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
    >
      <Card className="hover:shadow-md transition-shadow">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold">
                {deal.origin} → {deal.destination}
              </span>
              <Badge className={cabinColors[deal.cabin] || "bg-gray-100 text-gray-800"}>
                {deal.cabin.replace("_", " ")}
              </Badge>
            </div>
            <Badge variant="destructive" className="text-lg px-3 py-1">
              -{deal.discount_pct}%
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-3">
            <div>
              <p className="text-xs text-muted-foreground">Price</p>
              <p className="text-xl font-bold text-green-600">
                ${deal.price.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Avg Price</p>
              <p className="text-lg text-muted-foreground line-through">
                ${deal.avg_price.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Airline</p>
              <p className="text-sm font-medium">{deal.airline || "Multiple"}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Date</p>
              <p className="text-sm">
                {deal.outbound_date || "Flexible"}
                {deal.return_date && ` — ${deal.return_date}`}
              </p>
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            {deal.booking_url && (
              <a href={deal.booking_url} target="_blank" rel="noopener noreferrer">
                <Button size="sm">Book on Google Flights</Button>
              </a>
            )}
            <Button size="sm" variant="outline" onClick={handleDismiss}>
              Dismiss
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
