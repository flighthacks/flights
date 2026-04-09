"use client";

import { useEffect, useRef, useState, useCallback } from "react";
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
  const scanningRef = useRef(false);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const pollStatus = useCallback(async () => {
    try {
      const s = await api.getScanStatus();
      setStatus(s);
      if (s.running) {
        // Ensure we're in scanning state if backend says it's running
        setScanning(true);
        scanningRef.current = true;
      } else if (scanningRef.current) {
        // Was scanning, now stopped — scan completed
        setScanning(false);
        scanningRef.current = false;
        stopPolling();
        onComplete?.();
      }
    } catch {
      // ignore poll errors
    }
  }, [onComplete, stopPolling]);

  const startScan = async () => {
    try {
      await api.triggerScanAsync();
    } catch {
      // Scan may already be running — that's fine
    }
    setScanning(true);
    scanningRef.current = true;
    stopPolling();
    // Poll immediately, then every 1.5s
    pollStatus();
    intervalRef.current = setInterval(pollStatus, 1500);
  };

  useEffect(() => {
    // Check if a scan is already running on mount
    pollStatus();
    return stopPolling;
  }, [pollStatus, stopPolling]);

  const isRunning = scanning || (status?.running ?? false);

  return (
    <div className="space-y-2">
      <Button onClick={startScan} disabled={isRunning}>
        {isRunning ? "Scanning..." : "Scan Now"}
      </Button>

      <AnimatePresence>
        {isRunning && status && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
          >
            <Card>
              <CardContent className="p-4 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground truncate mr-2">
                    {status.current_route || "Starting scan..."}
                  </span>
                  <span className="font-medium whitespace-nowrap">
                    {status.routes_scanned}/{status.total_routes}
                  </span>
                </div>
                <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                  <motion.div
                    className="bg-primary h-2 rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.max(status.progress, 1)}%` }}
                    transition={{ duration: 0.5 }}
                  />
                </div>
                <div className="flex gap-4 text-xs text-muted-foreground">
                  <span>{status.observations_added} prices collected</span>
                  <span>{status.deals_found} deals found</span>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {!isRunning && status && status.observations_added > 0 && (
        <p className="text-sm text-muted-foreground">
          Last scan: {status.routes_scanned} routes, {status.observations_added} prices, {status.deals_found} deals
        </p>
      )}
    </div>
  );
}
