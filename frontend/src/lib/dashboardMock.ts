/**
 * Purpose: Placeholder data for the guarantor dashboard screens.
 * Dependencies: none.
 * Used by: the dashboard routes until guarantor accounts exist.
 *
 * The guarantor has no account model yet — email/OTP sign-up is still to come —
 * so these screens render seeded values. Replace each export with an API call
 * once a signed-in guarantor can be identified.
 */

export type GuaranteeStatus = "Active" | "Completed";

export type DashboardGuarantee = {
  id: string;
  workerName: string;
  workerRole: string;
  avatarUrl: string | null;
  jobTitle: string;
  amount: number;
  status: GuaranteeStatus;
  startedOn: string;
};

export type ActivityEntry = {
  id: string;
  label: string;
  at: string;
};

export type Notification = {
  id: string;
  title: string;
  body: string;
  at: string;
  icon: "bell" | "check" | "calendar";
  group: "Recent" | "Earlier";
};

export const guarantor = {
  firstName: "Daniel",
  fullName: "Daniel Peters",
  email: "danielpeters03@gmail.com",
  phone: "",
  address: "",
  initials: "DP",
};

export const actionRequired = {
  title: "Action required",
  body: "Jane A. requested you as a guarantor for a home cleaning job",
};

export const stats = [
  { id: "active", label: "Active Guarantees", value: 2 },
  // The design shows this card labelled "Active Guarantees" too; read as
  // completed until the designer confirms.
  { id: "completed", label: "Completed Guarantees", value: 2 },
];

export const guarantees: DashboardGuarantee[] = [
  {
    id: "g-1",
    workerName: "Jane A",
    workerRole: "Cleaner",
    avatarUrl: null,
    jobTitle: "Home cleaning",
    amount: 25000,
    status: "Active",
    startedOn: "23 sep 2026",
  },
  {
    id: "g-2",
    workerName: "Daniella k.",
    workerRole: "Pumber",
    avatarUrl: null,
    jobTitle: "Sink fix",
    amount: 15000,
    status: "Completed",
    startedOn: "23 sep 2026",
  },
];

export const recentActivity: ActivityEntry[] = [
  { id: "a-1", label: "Guarantee activated", at: "20/2/2026· 12:04:32" },
  { id: "a-2", label: "Identity verified", at: "20/2/2026· 12:04:32" },
];

export const notifications: Notification[] = [
  {
    id: "n-1",
    title: "Guarantee activated",
    body: "Lorem ipsum dolor sit amet, consectetur adipiscing elit",
    at: "1 hour ago",
    icon: "bell",
    group: "Recent",
  },
  {
    id: "n-2",
    title: "Identification verification completed",
    body: "Lorem ipsum dolor sit amet, consectetur adipiscing elit",
    at: "Yesterday",
    icon: "check",
    group: "Recent",
  },
  {
    id: "n-3",
    title: "Guarantee expires soon",
    body: "Lorem ipsum dolor sit amet, consectetur adipiscing elit",
    at: "2 days ago",
    icon: "calendar",
    group: "Recent",
  },
  {
    id: "n-4",
    title: "Guarantee activated",
    body: "Lorem ipsum dolor sit amet, consectetur adipiscing elit",
    at: "1 hour ago",
    icon: "bell",
    group: "Earlier",
  },
];

/** Formats an amount the way the designs show it: ₦25,000.00 */
export function formatNaira(amount: number) {
  return `₦${amount.toLocaleString("en-NG", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
