import { ReviewRequest } from "./ReviewRequest";

export const metadata = { title: "Guarantor request" };

export default async function ReviewPage({ params }: PageProps<"/guarantor/[id]/review">) {
  const { id } = await params;

  return <ReviewRequest instrumentId={id} />;
}
