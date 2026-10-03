import type { ReactNode } from "react";
import { JobsProvider } from "@/components/worker/JobsProvider";
import { WorkerNav } from "@/components/worker/WorkerNav";

export default function WorkerLayout({ children }: { children: ReactNode }) {
  return (
    <JobsProvider>
      <div className="mx-auto flex w-full max-w-md flex-col">
        {/* Room for the fixed tab bar. */}
        <div className="flex-1 pb-28">{children}</div>
        <WorkerNav />
      </div>
    </JobsProvider>
  );
}
