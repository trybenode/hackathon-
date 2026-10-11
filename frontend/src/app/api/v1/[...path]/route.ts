/** Same-origin streaming API bridge; preserves existing cookies and contracts while hiding server secrets. */
import { isIP } from "node:net";
import { getApiProxyOrigin } from "@/lib/serverApi";
import type { NextRequest } from "next/server";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const MAX_BODY_BYTES = 12 * 1024 * 1024;

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const origin = getApiProxyOrigin();
  const secret = process.env.INTERNAL_PROXY_SECRET;
  if (!origin || !secret)
    return Response.json(
      { detail: "API proxy is not configured.", code: "SERVICE_UNAVAILABLE" },
      { status: 503 },
    );
  const { path } = await context.params;
  const url = new URL(
    `/api/v1/${path.map(encodeURIComponent).join("/")}`,
    origin,
  );
  url.search = request.nextUrl.search;
  const headers = new Headers();
  for (const name of [
    "accept",
    "content-type",
    "cookie",
    "origin",
    "authorization",
    "x-api-key",
    "idempotency-key",
    "user-agent",
    "x-payscrow-signature",
    "x-payscrow-timestamp",
    "x-payscrow-delivery-id",
  ]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set("X-Trust-Proxy-Key", secret);
  // Enable only behind a managed edge that appends the actual peer to X-Forwarded-For.
  const hops = Number(process.env.PROXY_TRUSTED_HOPS ?? "0");
  const chain = (request.headers.get("x-forwarded-for") ?? "")
    .split(",")
    .map((ip) => ip.trim());
  const ip =
    Number.isInteger(hops) && hops > 0 ? chain[chain.length - hops] : undefined;
  if (ip && isIP(ip)) headers.set("X-Trust-Client-IP", ip);
  let body: Uint8Array | undefined;
  if (request.method !== "GET" && request.method !== "HEAD" && request.body) {
    const reader = request.body.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    try {
      while (true) {
        const result = await reader.read();
        if (result.done) break;
        size += result.value.byteLength;
        if (size > MAX_BODY_BYTES) {
          await reader.cancel();
          return Response.json(
            {
              detail: "Request exceeds the upload limit.",
              code: "PAYLOAD_TOO_LARGE",
            },
            { status: 413 },
          );
        }
        chunks.push(result.value);
      }
    } catch {
      return Response.json(
        { detail: "Request interrupted.", code: "REQUEST_INTERRUPTED" },
        { status: 400 },
      );
    }
    body = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      body.set(chunk, offset);
      offset += chunk.byteLength;
    }
  }
  try {
    const upstream = await fetch(url, {
      method: request.method,
      headers,
      body: body as BodyInit | undefined,
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(60000),
    });
    const outgoing = new Headers(upstream.headers);
    for (const name of [
      "connection",
      "transfer-encoding",
      "content-encoding",
      "content-length",
      "set-cookie",
    ])
      outgoing.delete(name);
    for (const cookie of upstream.headers.getSetCookie())
      outgoing.append("set-cookie", cookie);
    outgoing.set("Cache-Control", "no-store, private");
    outgoing.set("Referrer-Policy", "no-referrer");
    return new Response(upstream.body, {
      status: upstream.status,
      headers: outgoing,
    });
  } catch {
    // Do not log a URL: history and verification paths contain bearer tokens.
    return Response.json(
      {
        detail:
          "Service unavailable. Reconcile uncertain writes before retrying.",
        code: "UPSTREAM_UNAVAILABLE",
      },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}

export {
  proxy as GET,
  proxy as HEAD,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
  proxy as OPTIONS,
};
