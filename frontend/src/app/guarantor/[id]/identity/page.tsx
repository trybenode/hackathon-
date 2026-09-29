import { IdentityForm } from "./IdentityForm";

export const metadata = { title: "Identity information" };

export default async function IdentityPage({ params }: PageProps<"/guarantor/[id]/identity">) {
  const { id } = await params;

  return <IdentityForm instrumentId={id} />;
}
