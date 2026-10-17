/** Tenant reviewer workbench inside the existing developer shell. */
import { ReviewQueue } from "@/components/admission/ReviewQueue";
export const metadata = { robots: { index: false, follow: false } };
export default function Page() {
  return <ReviewQueue />;
}
