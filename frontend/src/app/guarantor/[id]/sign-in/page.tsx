import { SignInFlow } from "@/components/guarantor/SignInFlow";
import { ClaimInviteSignIn } from "./ClaimInviteSignIn";

export const metadata = { title: "Welcome" };

/**
 * Sits between accepting the request and submitting identity details. A
 * worker's invite link (`?claim=1`) comes here first instead, to find out who
 * the guarantor is before they review.
 */
export default async function OnboardingSignInPage({
  params,
  searchParams,
}: PageProps<"/guarantor/[id]/sign-in">) {
  const { id } = await params;
  const { email, claim } = await searchParams;

  if (claim === "1") return <ClaimInviteSignIn instrumentId={id} />;

  return (
    <SignInFlow
      redirectTo={`/guarantor/${id}/identity`}
      defaultEmail={typeof email === "string" ? email : ""}
    />
  );
}
