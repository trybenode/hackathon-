/** Presentation-only worker localization, using the shared preference without changing domain values. */
"use client";
import { usePathname } from "next/navigation";
import { useCallback } from "react";
import { useLanguage } from "@/components/history/LanguageProvider";
import { workerCopy } from "@/lib/workerLanguage";
export function useWorkerCopy(onlyWorker = false) {
  const pathname = usePathname();
  const { language } = useLanguage();
  const w = useCallback((text: string) => onlyWorker && !pathname.startsWith("/worker") ? text : workerCopy(language, text), [language, onlyWorker, pathname]);
  return { w, language };
}
