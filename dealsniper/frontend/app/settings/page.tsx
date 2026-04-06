"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { api, Settings } from "@/lib/api";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [newOrigin, setNewOrigin] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.getSettings().then(setSettings).catch(console.error);
  }, []);

  const save = async (updates: Partial<Settings>) => {
    setSaving(true);
    setMessage("");
    try {
      const updated = await api.updateSettings(updates);
      setSettings(updated);
      setMessage("Settings saved");
      setTimeout(() => setMessage(""), 2000);
    } catch {
      setMessage("Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const addOrigin = () => {
    if (!settings || !newOrigin) return;
    const code = newOrigin.toUpperCase().trim();
    if (code.length !== 3 || settings.origins.includes(code)) return;
    save({ origins: [...settings.origins, code] });
    setNewOrigin("");
  };

  const removeOrigin = (code: string) => {
    if (!settings) return;
    save({ origins: settings.origins.filter((o) => o !== code) });
  };

  if (!settings) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Settings</h1>
        <div className="h-64 animate-pulse bg-muted rounded" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Settings</h1>
        {message && (
          <p className="text-sm text-green-600 font-medium">{message}</p>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Departure Airports</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {settings.origins.map((origin) => (
              <Badge
                key={origin}
                variant="secondary"
                className="text-sm px-3 py-1 cursor-pointer hover:bg-destructive hover:text-destructive-foreground transition-colors"
                onClick={() => removeOrigin(origin)}
              >
                {origin} ×
              </Badge>
            ))}
          </div>
          <div className="flex gap-2 max-w-xs">
            <Input
              placeholder="Airport code (e.g. SYD)"
              value={newOrigin}
              onChange={(e) => setNewOrigin(e.target.value)}
              maxLength={3}
              onKeyDown={(e) => e.key === "Enter" && addOrigin()}
            />
            <Button onClick={addOrigin} disabled={!newOrigin}>
              Add
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Scan Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label>Deal Threshold</Label>
              <p className="text-xs text-muted-foreground mb-1">
                Alert when price is at or below this % of the 30-day average
              </p>
              <div className="flex gap-2 items-center">
                <Input
                  type="number"
                  step="0.05"
                  min="0.1"
                  max="1.0"
                  value={settings.deal_threshold}
                  onChange={(e) =>
                    setSettings({ ...settings, deal_threshold: parseFloat(e.target.value) })
                  }
                  className="w-24"
                />
                <span className="text-sm text-muted-foreground">
                  ({Math.round((1 - settings.deal_threshold) * 100)}% discount)
                </span>
              </div>
            </div>

            <div>
              <Label>Scan Interval (hours)</Label>
              <p className="text-xs text-muted-foreground mb-1">
                How often to run automatic scans
              </p>
              <Input
                type="number"
                min="1"
                max="168"
                value={settings.scan_interval_hours}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    scan_interval_hours: parseInt(e.target.value),
                  })
                }
                className="w-24"
              />
            </div>

            <div>
              <Label>Lookahead (days)</Label>
              <p className="text-xs text-muted-foreground mb-1">
                How far ahead to search for flights
              </p>
              <Input
                type="number"
                min="7"
                max="365"
                value={settings.lookahead_days}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    lookahead_days: parseInt(e.target.value),
                  })
                }
                className="w-24"
              />
            </div>

            <div>
              <Label>Min Observations Before Alert</Label>
              <p className="text-xs text-muted-foreground mb-1">
                Minimum data points needed before deals are flagged
              </p>
              <Input
                type="number"
                min="1"
                max="100"
                value={settings.min_observations_before_alert}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    min_observations_before_alert: parseInt(e.target.value),
                  })
                }
                className="w-24"
              />
            </div>
          </div>

          <Separator />

          <Button
            onClick={() =>
              save({
                deal_threshold: settings.deal_threshold,
                scan_interval_hours: settings.scan_interval_hours,
                lookahead_days: settings.lookahead_days,
                min_observations_before_alert: settings.min_observations_before_alert,
              })
            }
            disabled={saving}
          >
            {saving ? "Saving..." : "Save Settings"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
