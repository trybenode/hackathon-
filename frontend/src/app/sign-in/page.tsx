import { SignInFlow } from "@/components/guarantor/SignInFlow";

export const metadata = { title: "Welcome" };

/** Returning guarantors land straight on their dashboard, never on review. */
export default function SignInPage() {
  return <SignInFlow redirectTo="/dashboard" />;
}
