import { WorkerLiveness } from "./WorkerLiveness";

export const metadata = { title: "Liveness check" };

export default function JoinLivenessPage() {
  return <WorkerLiveness />;
}
