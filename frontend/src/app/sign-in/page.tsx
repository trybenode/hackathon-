import { SignInFlow } from "@/components/guarantor/SignInFlow";

export const metadata = { title: "Welcome" };

/**
 * Returning guarantors land on their dashboard, never on review. A screen that
 * sent someone here to sign in passes `next` to bring them back afterwards;
 * only same-site paths are honoured, so the link cannot send anyone elsewhere.
 */
export default async function SignInPage({ searchParams }: PageProps<"/sign-in">) {
  const { next } = await searchParams;
  const target =
    typeof next === "string" && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";

  return <SignInFlow redirectTo={target} />;
}
