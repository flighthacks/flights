"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, ScanStatus } from "@/lib/api";

interface ScanProgressProps {
  onComplete?: () => void;
}

export default function ScanProgress({ onComplete }: ScanProgressProps) {
  const [status, setStatus] = useState<ScanStatus | null>(null);
  const [scanning, setScanning] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const pollStatus = async () => {
    try {
      const s = await api.getScanStatus();
      setStatus(s);
      if (!s.running && scanning) {
        setScanning(false);
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        onComplete?.();
      }
    } catch {
      // ignore poll errors
    }
  };

  const startScan = async () => {
    try {
      await api.triggerScanAsync();
      setScanning(true);
      intervalRef.current = setInterval(pollStatus, 2000);
    } catch {
      // Scan may already be running
      setScanning(true);
      intervalRef.current = setInterval(pollStatus, 2000);
    }
  };

  useEffect(() => {
    pollStatus();
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-2">
      <Button onClick={startScan} disabled={scanning || (status?.running ?? false)}>
        {scanning || status?.running ? "Scanning..." : "Scan Now"}
      </Button>

      <AnimatePresence>
        {(scanning || status?.running) && status && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
          >
            <Card>
              <CardContent className="p-4 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">
                    {status.current_route || "Starting..."}
                  </span>
                  <span className="font-medium">
                    {status.routes_scanned}/{status.total_routes}
                  </span>
                </div>
                <div className="w-full bg-muted rounded-full h-2">
                  <motion.div
                    className="bg-primary h-2 rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${status.progress}%` }}
                    transition={{ duration: 0.5 }}
                  />
                </div>
                <div className="flex gap-4 text-xs text-muted-foreground">
                  <span>{status.observations_added} prices</span>
                  <span>{status.deals_found} deals</span>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {!scanning && !status?.running && status && status.observations_added > 0 && (
        <p className="text-sm text-muted-foreground">
          Last scan: {status.routes_scanned} routes, {status.observations_added} prices, {status.deals_found} deals
        </p>
      )}
    </div>
  );
}
