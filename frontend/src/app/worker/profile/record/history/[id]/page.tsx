import { LanguageSelector } from "@/components/history/LanguageProvider";
import Link from "next/link";
import { ClarificationThread } from "@/components/history/ClarificationThread";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <main className="mx-auto flex max-w-xl flex-col gap-5 p-5">
      <Link href="/worker/profile/record/history">←</Link>
      <LanguageSelector />
      <ClarificationThread
        base={`/me/history-claims/${encodeURIComponent(id)}`}
      />
    </main>
  );
}
