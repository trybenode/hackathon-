import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  logging: { fetches: { fullUrl: false }, incomingRequests: { ignore: [/^\/verify\//, /^\/confirm-work\//, /^\/api\/v1\//] } },
  async headers() {
    return ["/verify/:token", "/confirm-work/:token"].map(source => ({ source, headers: [
      { key: "Cache-Control", value: "no-store, private" },
      { key: "Referrer-Policy", value: "no-referrer" },
      { key: "X-Robots-Tag", value: "noindex, nofollow" },
    ] }));
  },
};

export default nextConfig;
