import type { ReactNode } from "react";
import { DeveloperShell } from "@/components/developer/DeveloperShell";

export default function DeveloperLayout({ children }: { children: ReactNode }) {
  return <DeveloperShell>{children}</DeveloperShell>;
}
