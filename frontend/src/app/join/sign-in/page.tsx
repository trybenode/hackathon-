import { SignInFlow } from "@/components/guarantor/SignInFlow";

export const metadata = { title: "Welcome" };

/**
 * A new worker's email and code. The account is made here; a returning worker
 * lands wherever their verification left off (see `landingPathFor`).
 */
export default function JoinSignInPage() {
  return <SignInFlow signUp="worker" />;
}
