import { LanguageSelector } from "@/components/history/LanguageProvider";
import type { ReactNode } from "react";
import { DemoBanner } from "@/components/worker/DemoBanner";
import { WorkerNav } from "@/components/worker/WorkerNav";

export default function WorkerLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex w-full max-w-md flex-col">
      <DemoBanner />
      <div className="px-6 pt-3"><LanguageSelector /></div>
      {/* Room for the fixed tab bar. */}
      <div className="flex-1 pb-28">{children}</div>
      <WorkerNav />
    </div>
  );
}
