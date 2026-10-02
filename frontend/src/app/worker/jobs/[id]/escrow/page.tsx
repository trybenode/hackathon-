import { EscrowStatus } from "./EscrowStatus";

export const metadata = { title: "Escrow" };

export default async function EscrowPage({ params }: PageProps<"/worker/jobs/[id]/escrow">) {
  const { id } = await params;

  return <EscrowStatus jobId={id} />;
}
