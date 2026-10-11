/** Resolve the server-only API destination at runtime; used by the proxy, readiness and public SSR. */
import "server-only";

export function getApiProxyOrigin(): string | undefined {
  const origin = process.env.BACKEND_URL ?? process.env.API_PROXY_ORIGIN ?? (process.env.API_PROXY_HOSTPORT ? `http://${process.env.API_PROXY_HOSTPORT}` : undefined);
  if (!origin) return undefined;
  try {
    const url = new URL(origin);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash || !["", "/"].includes(url.pathname)) return undefined;
    return url.origin;
  } catch { return undefined; }
}
