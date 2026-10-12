"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Day = { day: string; total: number; successful: number };

// SVG attributes cannot read CSS variables, so the design tokens are spelled
// out: primary-500, error-mid, stroke, grey-600 and primary-50.
const COLORS = { successful: "#06b6e9", failed: "#f14d4d", grid: "#e7e5e4", axis: "#727272", hover: "#e6f8fe" };

function label(day: string) {
  // The API sends UTC calendar days; format them without shifting the date.
  return new Date(`${day}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}

/** Calls per day over the last two weeks: successful and failed, stacked. */
export function UsageChart({ daily }: { daily: Day[] }) {
  const data = daily.map((entry) => ({
    day: label(entry.day),
    Successful: entry.successful,
    Failed: entry.total - entry.successful,
  }));

  return (
    <div className="h-64 w-full" role="img" aria-label="API calls per day over the last 14 days">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -24 }}>
          <CartesianGrid vertical={false} stroke={COLORS.grid} />
          <XAxis
            dataKey="day"
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
            tick={{ fontSize: 11, fill: COLORS.axis }}
          />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: COLORS.axis }} />
          <Tooltip cursor={{ fill: COLORS.hover }} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
          <Bar dataKey="Successful" stackId="calls" fill={COLORS.successful} radius={[0, 0, 0, 0]} />
          <Bar dataKey="Failed" stackId="calls" fill={COLORS.failed} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
