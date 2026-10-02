"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { initialJobs, type WorkerJob } from "@/lib/workerMock";

type JobsContextValue = {
  jobs: WorkerJob[];
  getJob: (id: string) => WorkerJob | undefined;
  /** The worker says the work is done; funds wait for the client. */
  markComplete: (id: string) => void;
  /** The worker raises an issue; funds stay held for review (FR-7.3). */
  reportIssue: (id: string, reason: string, complaint: string) => void;
};

const JobsContext = createContext<JobsContextValue | null>(null);

/**
 * Holds the mock jobs for the worker screens.
 *
 * Lives in the worker layout, so an action taken on Job Details is still true
 * on the escrow screen. In memory only: a full reload starts over, which is
 * fine for mock data and avoids hydration mismatches.
 */
export function JobsProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<WorkerJob[]>(initialJobs);

  const update = useCallback((id: string, change: (job: WorkerJob) => WorkerJob) => {
    setJobs((current) => current.map((job) => (job.id === id ? change(job) : job)));
  }, []);

  const value = useMemo<JobsContextValue>(
    () => ({
      jobs,
      getJob: (id) => jobs.find((job) => job.id === id),
      markComplete: (id) =>
        update(id, (job) => ({
          ...job,
          escrowStage: "awaiting_confirmation",
          completedAt: new Date().toISOString(),
        })),
      reportIssue: (id, reason, complaint) =>
        update(id, (job) => {
          const now = new Date().toISOString();
          return {
            ...job,
            escrowStage: "disputed",
            // Reporting an issue implies the work was attempted, which is
            // also how the normaliser reads a dispute.
            completedAt: job.completedAt ?? now,
            dispute: {
              id: `D-${1000 + Math.floor(Math.random() * 9000)}`,
              submittedAt: now,
              reason,
              complaint,
            },
          };
        }),
    }),
    [jobs, update],
  );

  return <JobsContext.Provider value={value}>{children}</JobsContext.Provider>;
}

export function useJobs() {
  const context = useContext(JobsContext);
  if (!context) throw new Error("useJobs must be used inside JobsProvider");
  return context;
}
