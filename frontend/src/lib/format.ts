/**
 * Purpose: Format values the way the guarantor designs show them.
 * Dependencies: none.
 * Used by: the dashboard screens.
 */

/** Formats a byte count as "120 KB". */
export function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes < 0) return "0 KB";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  const rounded = size >= 10 || unit === 0 ? Math.round(size) : Math.round(size * 10) / 10;
  return `${rounded} ${units[unit]}`;
}

/** Formats an amount as ₦25,000.00. Amounts arrive as decimal strings. */
export function formatNaira(amount: string | number | null | undefined) {
  if (amount === null || amount === undefined) return "—";
  const value = typeof amount === "string" ? Number(amount) : amount;
  if (Number.isNaN(value)) return "—";

  return `₦${value.toLocaleString("en-NG", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/** "23 sep 2026", matching the designs. */
export function formatStartedOn(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";

  return date
    .toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" })
    .replace(/(\w{3})/, (month) => month.toLowerCase());
}

/** "20/2/2026· 12:04:32", matching the recent activity list. */
export function formatActivityTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return `${date.toLocaleDateString("en-GB")}· ${date.toLocaleTimeString("en-GB")}`;
}

/** "1 hour ago", "Yesterday", "2 days ago" for the alerts list. */
export function formatRelative(value: string, now: Date = new Date()) {
  const date = new Date(value);
  const minutes = Math.round((now.getTime() - date.getTime()) / 60000);

  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;

  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;

  const days = Math.round(hours / 24);
  if (days === 1) return "Yesterday";
  if (days < 30) return `${days} days ago`;

  return date.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}
