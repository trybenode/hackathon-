import { JobDetails } from "./JobDetails";

export const metadata = { title: "Job details" };

export default async function JobDetailsPage({ params }: PageProps<"/worker/jobs/[id]">) {
  const { id } = await params;

  return <JobDetails jobId={id} />;
}
