import type { Metadata } from "next";
import { RecipientForm } from "./RecipientForm";
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Confirm work history", robots: { index: false, follow: false }, referrer: "no-referrer" };
export default async function Page({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  if (!/^[A-Za-z0-9_-]{32,128}$/.test(token)) return <main className="p-6">This confirmation link is invalid.</main>;
  return <RecipientForm token={token} />;
}
