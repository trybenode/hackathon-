import { AgreementView } from "./AgreementView";

export const metadata = { title: "Agreement" };

export default async function AgreementPage({ params }: PageProps<"/guarantor/[id]/agreement">) {
  const { id } = await params;

  return <AgreementView instrumentId={id} />;
}
