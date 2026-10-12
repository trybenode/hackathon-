"use client";

import { useCallback } from "react";
import { SignInFlow } from "@/components/guarantor/SignInFlow";
import { claimInvite } from "@/lib/guarantor";

/**
 * Sign-in for someone opening a worker's invite link: any address works, the
 * account is made if new, and signing in claims the invite before review.
 */
export function ClaimInviteSignIn({ instrumentId }: { instrumentId: string }) {
  const claim = useCallback(async () => {
    await claimInvite(instrumentId);
  }, [instrumentId]);

  return <SignInFlow signUp="guarantor" onSignedIn={claim} redirectTo={`/guarantor/${instrumentId}/review`} />;
}
