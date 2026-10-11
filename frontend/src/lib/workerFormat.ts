/**
 * Purpose: Format names, money and dates the way the worker designs show them.
 * Dependencies: none.
 * Used by: the worker jobs, escrow, profile and portable record screens.
 */

export function initialsOf(name: string) {
  return name
    .split(" ")
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

// Formatting helpers. lib/format.ts carries the same on the guarantor branch;
// they live here so this branch does not edit a file that one changes. Fold
// them back into lib/format.ts after that branch merges.

/** ₦25,000.00 */
export function formatNaira(amount: number, language = "en") {
  return `₦${amount.toLocaleString(`${language}-NG`, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** 12:04:32 */
export function formatTime(value: string, language = "en") {
  if (language !== "en") return new Intl.DateTimeFormat(`${language}-NG`, { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Africa/Lagos" }).format(new Date(value));
  return new Date(value).toLocaleTimeString("en-GB", { hour12: false });
}

// Month names are spelled out rather than taken from the browser locale,
// which abbreviates them differently ("Sep" vs "Sept") from one runtime to
// the next. The designs use both forms, in different places.
const SHORT_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
const LONG_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sept", "Oct", "Nov", "Dec"];

/** 29 sep 2026 */
export function formatShortDate(value: string, language = "en") {
  if (language !== "en") return new Intl.DateTimeFormat(`${language}-NG`, {day:"numeric",month:"short",year:"numeric",timeZone:"Africa/Lagos"}).format(new Date(value));
  const date = new Date(value);
  return `${date.getDate()} ${SHORT_MONTHS[date.getMonth()]} ${date.getFullYear()}`;
}

/** Sept 29, 2026 */
export function formatLongDate(value: string, language = "en") {
  if (language !== "en") return new Intl.DateTimeFormat(`${language}-NG`, {day:"numeric",month:"long",year:"numeric",timeZone:"Africa/Lagos"}).format(new Date(value));
  const date = new Date(value);
  return `${LONG_MONTHS[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
}

/** 12:00PM */
export function formatClock(value: string, language = "en") {
  if (language !== "en") return new Intl.DateTimeFormat(`${language}-NG`, {hour:"numeric",minute:"2-digit",timeZone:"Africa/Lagos"}).format(new Date(value));
  const date = new Date(value);
  const hours = date.getHours() % 12 || 12;
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${hours}:${minutes}${date.getHours() < 12 ? "AM" : "PM"}`;
}

/** 29, Sep */
export function formatDayMonth(value: string, language = "en") {
  if (language !== "en") return new Intl.DateTimeFormat(`${language}-NG`, {day:"numeric",month:"short",timeZone:"Africa/Lagos"}).format(new Date(value));
  const date = new Date(value);
  return `${date.getDate()}, ${LONG_MONTHS[date.getMonth()].slice(0, 3)}`;
}

/** 20 Nov, 2026 */
export function formatDayMonthYear(value: string, language = "en") {
  if (language !== "en") return new Intl.DateTimeFormat(`${language}-NG`, {day:"numeric",month:"short",year:"numeric",timeZone:"Africa/Lagos"}).format(new Date(value));
  const date = new Date(value);
  return `${date.getDate()} ${LONG_MONTHS[date.getMonth()].slice(0, 3)}, ${date.getFullYear()}`;
}

const FULL_MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/** 23 September, 2026 */
export function formatFullDate(value: string, language = "en") {
  if (language !== "en") return new Intl.DateTimeFormat(`${language}-NG`, {day:"numeric",month:"long",year:"numeric",timeZone:"Africa/Lagos"}).format(new Date(value));
  const date = new Date(value);
  return `${date.getDate()} ${FULL_MONTHS[date.getMonth()]}, ${date.getFullYear()}`;
}
