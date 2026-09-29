import { LivenessCheck } from "./LivenessCheck";

export const metadata = { title: "Liveness check" };

export default async function LivenessPage({ params }: PageProps<"/guarantor/[id]/liveness">) {
  const { id } = await params;

  return <LivenessCheck instrumentId={id} />;
}
