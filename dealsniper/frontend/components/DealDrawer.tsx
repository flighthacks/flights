"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MapDeal } from "@/lib/api";

interface DealDrawerProps {
  deal: MapDeal | null;
  onClose: () => void;
}

export default function DealDrawer({ deal, onClose }: DealDrawerProps) {
  return (
    <AnimatePresence>
      {deal && (
        <motion.div
          initial={{ y: "100%" }}
          animate={{ y: 0 }}
          exit={{ y: "100%" }}
          transition={{ type: "spring", damping: 25, stiffness: 300 }}
          className="absolute bottom-0 left-0 right-0 z-20 bg-background border-t rounded-t-xl shadow-lg p-6"
        >
          <div className="max-w-2xl mx-auto">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <h3 className="text-xl font-bold">
                  {deal.origin} → {deal.destination}
                </h3>
                <Badge variant="destructive" className="text-base px-2 py-0.5">
                  -{deal.discount_pct}%
                </Badge>
              </div>
              <Button variant="ghost" size="sm" onClick={onClose}>
                ✕
              </Button>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div>
                <p className="text-xs text-muted-foreground">Deal Price</p>
                <p className="text-2xl font-bold text-green-500">
                  ${deal.price.toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Average Price</p>
                <p className="text-lg text-muted-foreground line-through">
                  ${deal.avg_price.toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Airline</p>
                <p className="text-sm font-medium">{deal.airline || "Various"}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Cabin</p>
                <p className="text-sm font-medium capitalize">
                  {deal.cabin.replace("_", " ")}
                </p>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                {deal.outbound_date || "Flexible dates"}
                {deal.return_date && ` — ${deal.return_date}`}
              </span>
              {deal.booking_url && (
                <a href={deal.booking_url} target="_blank" rel="noopener noreferrer">
                  <Button>Book on Google Flights</Button>
                </a>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
