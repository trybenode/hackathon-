import { SkipIfSignedIn } from "@/components/auth/SkipIfSignedIn";
import { JoinIntro } from "./JoinIntro";

export const metadata = { title: "Verify your identity" };

/** A worker who already has an account goes to their step or Home instead. */
export default function JoinPage() {
  return (
    <SkipIfSignedIn to="worker">
      <JoinIntro />
    </SkipIfSignedIn>
  );
}
