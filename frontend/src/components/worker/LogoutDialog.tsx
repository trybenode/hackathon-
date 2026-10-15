"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui";
import { SignOutIcon } from "@/components/developer/icons";
import { signOut } from "@/lib/guarantor";
import { WorkerDialog } from "./WorkerDialog";

/** "Are you sure you want to log out?", then back to the landing page. */
export function LogoutDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [leaving, setLeaving] = useState(false);

  async function confirm() {
    setLeaving(true);
    // Even if the server can't be reached, the visitor asked to leave.
    await signOut().catch(() => undefined);
    router.replace("/");
  }

  return (
    <WorkerDialog open={open} onClose={onClose} label="Log out">
      <div className="flex flex-col items-center gap-5 text-center">
        <span className="flex h-16 w-16 items-center justify-center rounded-pill bg-error-mid text-white">
          <SignOutIcon width={28} height={28} />
        </span>
        <h2 className="text-body-lg font-semibold text-grey-900">Log out</h2>
        <p className="text-body-md text-grey-900">Are you sure you want to log out?</p>
        <div className="mt-2 flex w-full gap-4">
          <Button variant="outline" size="lg" fullWidth className="min-w-0 px-0" disabled={leaving} onClick={onClose}>
            Cancel
          </Button>
          <Button size="lg" fullWidth className="min-w-0 px-0" disabled={leaving} onClick={confirm}>
            {leaving ? "Logging out…" : "Confirm"}
          </Button>
        </div>
      </div>
    </WorkerDialog>
  );
}
