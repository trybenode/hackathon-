"use client";

import { getWorkerRecord } from "@/lib/workerRecord";
import { useWorkerResource } from "./useWorkerResource";

/** The signed-in worker's portable record. */
export function useWorkerRecord() {
  return useWorkerResource(getWorkerRecord, "This account has no worker profile.");
}
