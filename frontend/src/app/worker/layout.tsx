import { cookies } from "next/headers";
import { ReviewLanguageProvider } from "@/components/admission/ReviewLanguage";
import type { ReactNode } from "react";
import { DemoBanner } from "@/components/worker/DemoBanner";
import { WorkerNav } from "@/components/worker/WorkerNav";

export default async function WorkerLayout({
  children,
}: {
  children: ReactNode;
}) {
  const value = (await cookies()).get("history_language")?.value;
  const language =
    value === "yo" || value === "ha" || value === "ig" ? value : "en";
  return (
    <ReviewLanguageProvider initialLanguage={language}>
      <div className="mx-auto flex w-full max-w-md flex-col">
        <DemoBanner />
        {/* Room for the fixed tab bar. */}
        <div className="flex-1 pb-28">{children}</div>
        <WorkerNav />
      </div>
    </ReviewLanguageProvider>
  );
}
