import { guarantorStates, workerRecord } from "@/lib/workerRecordMock";
import { CredentialList } from "./CredentialList";

export const metadata = { title: "Verified credentials" };

/**
 * `?guarantor=expired` previews the expired-guarantee state the designs also
 * cover, until real data drives it.
 */
export default async function CredentialsPage({
  searchParams,
}: PageProps<"/worker/profile/record/credentials">) {
  const { guarantor } = await searchParams;
  const credentials =
    guarantor === "expired"
      ? { ...workerRecord.credentials, guarantor: guarantorStates.expired }
      : workerRecord.credentials;

  return <CredentialList credentials={credentials} />;
}
