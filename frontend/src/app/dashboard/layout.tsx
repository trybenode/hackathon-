import type { ReactNode } from "react";
import { BottomNav } from "@/components/dashboard/BottomNav";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex w-full max-w-md flex-col">
      {/* Room for the fixed tab bar. */}
      <div className="flex-1 pb-28">{children}</div>
      <BottomNav />
    </div>
  );
}
