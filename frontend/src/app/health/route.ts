/** Managed frontend readiness checks the same backend dependencies used by browser journeys. */
import { getApiProxyOrigin } from "@/lib/serverApi";
export const dynamic = "force-dynamic";
export async function GET(): Promise<Response> {
  const origin = getApiProxyOrigin();
  if (origin && (process.env.INTERNAL_PROXY_SECRET?.length ?? 0) >= 32) {
    try {
      const upstream = await fetch(`${origin}/api/v1/health/ready`, { cache: "no-store", signal: AbortSignal.timeout(8000) });
      if (upstream.ok) return Response.json({ status: "ready" }, { headers: { "Cache-Control": "no-store" } });
    } catch { /* Never log destination credentials or provider details. */ }
  }
  return Response.json({ status: "unavailable" }, { status: 503, headers: { "Cache-Control": "no-store" } });
}
