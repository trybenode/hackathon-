"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui";
import { errorMessage, featureRequest, type Page } from "@/lib/portability";

type Job = { id: string; title: string; status: string; created_at: string };

export default function CustomerJobs() {
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState<Page<Job> | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    featureRequest<Page<Job>>(`/me/client/jobs?page=${page}`, { signal: controller.signal }).then(value => { if (!controller.signal.aborted) { setData(value); setError(""); } }).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)); });
    return () => controller.abort();
  }, [page, revision]);
  return <main className="mx-auto flex w-full max-w-lg flex-col gap-5 p-6"><h1 className="text-h3 font-semibold">Your hired jobs</h1><p className="text-body-sm text-grey-600">Reviews require confirmed completion and stored protection evidence. Open a job to check its eligibility.</p>{error && <p role="alert">{error}</p>}{!data && !error && <p role="status">Loading your jobs…</p>}{data && <>{data.total === 0 && <p>No jobs are attributed to this account yet.</p>}<ul className="space-y-3">{data.items.map(job => <li key={job.id} className="rounded-xl border border-stroke p-4"><h2 className="font-semibold">{job.title}</h2><p className="mt-2 text-body-sm">{job.status.replaceAll("_", " ")}</p><Link className="mt-3 inline-block min-h-11 text-info underline" href={`/client/jobs/${job.id}/review`}>Check eligibility / review job</Link></li>)}</ul>{data.pages > 1 && <nav aria-label="Job pages" className="flex justify-between"><Button variant="outline" disabled={page === 1} onClick={() => setPage(value => value - 1)}>Previous</Button><span>{data.page} / {data.pages}</span><Button variant="outline" disabled={page >= data.pages} onClick={() => setPage(value => value + 1)}>Next</Button></nav>}</>}<Button variant="outline" onClick={() => setRevision(value => value + 1)}>Refresh jobs</Button></main>;
}
