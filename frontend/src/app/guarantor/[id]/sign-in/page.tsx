import { SignInFlow } from "@/components/guarantor/SignInFlow";

export const metadata = { title: "Welcome" };

/** Sits between accepting the request and submitting identity details. */
export default async function OnboardingSignInPage({
  params,
  searchParams,
}: PageProps<"/guarantor/[id]/sign-in">) {
  const { id } = await params;
  const { email } = await searchParams;

  return (
    <SignInFlow
      redirectTo={`/guarantor/${id}/identity`}
      defaultEmail={typeof email === "string" ? email : ""}
    />
  );
}
