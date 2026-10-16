/**
 * A link the API built, moved onto the address this page is served from.
 *
 * The API builds links from FRONTEND_BASE_URL, which can be stale or a
 * placeholder on a new deployment; the page's own origin is always right for
 * links people copy from it. Emails still rely on the setting.
 */
export function onThisSite(link: string): string {
  if (typeof window === "undefined") return link;
  try {
    const url = new URL(link);
    return `${window.location.origin}${url.pathname}${url.search}${url.hash}`;
  } catch {
    return link;
  }
}
