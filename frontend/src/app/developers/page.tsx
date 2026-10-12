import { SkipIfSignedIn } from "@/components/auth/SkipIfSignedIn";
import { DeveloperSignUp } from "./DeveloperSignUp";

export const metadata = { title: "Get started with our API" };

/** A developer who is already signed in goes to the dashboard instead. */
export default function DevelopersPage() {
  return (
    <SkipIfSignedIn to="developer">
      <DeveloperSignUp />
    </SkipIfSignedIn>
  );
}
