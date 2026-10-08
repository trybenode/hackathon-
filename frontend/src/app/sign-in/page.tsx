import { SignInFlow } from "@/components/guarantor/SignInFlow";

export const metadata = { title: "Welcome" };

/**
 * Lands each account on its own side of the app (see `landingPathFor`). A
 * screen that sent someone here to sign in passes `next` to bring them back
 * afterwards; only same-site paths are honoured, so the link cannot send
 * anyone elsewhere.
 */
export default async function SignInPage({ searchParams }: PageProps<"/sign-in">) {
  const { next } = await searchParams;
  const target =
    typeof next === "string" && next.startsWith("/") && !next.startsWith("//") ? next : undefined;

  return <SignInFlow redirectTo={target} />;
}
