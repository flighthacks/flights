"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

interface RouteFormProps {
  onCreated?: () => void;
}

export default function RouteForm({ onCreated }: RouteFormProps) {
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [cabin, setCabin] = useState("economy");
  const [tripType, setTripType] = useState("oneway");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!origin) return;
    setLoading(true);
    try {
      await api.createRoute({
        origin: origin.toUpperCase(),
        destination: destination ? destination.toUpperCase() : "ANYWHERE",
        cabin,
        trip_type: tripType,
      });
      setOrigin("");
      setDestination("");
      onCreated?.();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Add Monitored Route</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="grid grid-cols-2 md:grid-cols-5 gap-3 items-end">
          <div>
            <Label htmlFor="origin">Origin</Label>
            <Input
              id="origin"
              placeholder="PER"
              value={origin}
              onChange={(e) => setOrigin(e.target.value)}
              maxLength={3}
            />
          </div>
          <div>
            <Label htmlFor="destination">Destination</Label>
            <Input
              id="destination"
              placeholder="Leave empty for Anywhere"
              value={destination}
              onChange={(e) => setDestination(e.target.value)}
              maxLength={3}
            />
          </div>
          <div>
            <Label>Cabin</Label>
            <Select value={cabin} onValueChange={(v) => v && setCabin(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="economy">Economy</SelectItem>
                <SelectItem value="premium_economy">Premium Economy</SelectItem>
                <SelectItem value="business">Business</SelectItem>
                <SelectItem value="first">First</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Trip Type</Label>
            <Select value={tripType} onValueChange={(v) => v && setTripType(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="return">Return</SelectItem>
                <SelectItem value="oneway">One Way</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button type="submit" disabled={loading || !origin}>
            {loading ? "Adding..." : "Add Route"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
