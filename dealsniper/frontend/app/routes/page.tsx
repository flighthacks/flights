"use client";

import { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import RouteForm from "@/components/RouteForm";
import PriceChart from "@/components/PriceChart";
import { api, MonitoredRoute } from "@/lib/api";

export default function RoutesPage() {
  const [routes, setRoutes] = useState<MonitoredRoute[]>([]);
  const [selectedRoute, setSelectedRoute] = useState<MonitoredRoute | null>(null);

  const loadRoutes = useCallback(() => {
    api.getRoutes().then(setRoutes).catch(console.error);
  }, []);

  useEffect(() => {
    loadRoutes();
  }, [loadRoutes]);

  const handleToggle = async (id: number) => {
    await api.toggleRoute(id);
    loadRoutes();
  };

  const handleDelete = async (id: number) => {
    await api.deleteRoute(id);
    loadRoutes();
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Monitored Routes</h1>

      <RouteForm onCreated={loadRoutes} />

      <Card>
        <CardHeader>
          <CardTitle>Active Routes</CardTitle>
        </CardHeader>
        <CardContent>
          {routes.length === 0 ? (
            <p className="text-muted-foreground text-sm py-4">
              No routes configured. Add one above to start monitoring.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Route</TableHead>
                  <TableHead>Cabin</TableHead>
                  <TableHead>Trip</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Added</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {routes.map((route) => (
                  <TableRow
                    key={route.id}
                    className="cursor-pointer"
                    onClick={() => setSelectedRoute(route)}
                  >
                    <TableCell className="font-medium">
                      {route.origin} → {route.destination}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{route.cabin}</Badge>
                    </TableCell>
                    <TableCell>{route.trip_type}</TableCell>
                    <TableCell>
                      <Badge variant={route.active ? "default" : "outline"}>
                        {route.active ? "Active" : "Paused"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(route.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex gap-2 justify-end" onClick={(e) => e.stopPropagation()}>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleToggle(route.id)}
                        >
                          {route.active ? "Pause" : "Resume"}
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleDelete(route.id)}
                        >
                          Delete
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {selectedRoute && (
        <PriceChart
          origin={selectedRoute.origin}
          destination={selectedRoute.destination}
          cabin={selectedRoute.cabin}
        />
      )}
    </div>
  );
}
