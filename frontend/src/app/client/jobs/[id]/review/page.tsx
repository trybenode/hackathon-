import { ReviewForm } from "./ReviewForm";
export const metadata = {
  title: "Review a protected job",
  robots: { index: false, follow: false },
};
export default async function ReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ReviewForm jobId={id} />;
}
