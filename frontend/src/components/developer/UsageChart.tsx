"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Day = { day: string; total: number; successful: number };

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
    <div className="h-48 w-full" role="img" aria-label="API calls per day over the last 14 days">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -24 }}>
          <CartesianGrid vertical={false} stroke="var(--color-stroke)" />
          <XAxis
            dataKey="day"
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
            tick={{ fontSize: 11, fill: "var(--color-grey-600)" }}
          />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--color-grey-600)" }} />
          <Tooltip cursor={{ fill: "var(--color-primary-50)" }} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
          <Bar dataKey="Successful" stackId="calls" fill="var(--color-primary-500)" radius={[0, 0, 0, 0]} />
          <Bar dataKey="Failed" stackId="calls" fill="var(--color-error-mid)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
