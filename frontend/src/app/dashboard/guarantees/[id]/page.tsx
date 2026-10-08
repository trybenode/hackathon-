import { GuaranteeDetails } from "./GuaranteeDetails";

export const metadata = { title: "Guarantee details" };

export default async function GuaranteeDetailsPage({
  params,
}: PageProps<"/dashboard/guarantees/[id]">) {
  const { id } = await params;

  return <GuaranteeDetails instrumentId={id} />;
}
