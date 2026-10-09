import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  logging: { fetches: { fullUrl: false }, incomingRequests: { ignore: [/^\/verify\//] } },
  async headers() {
    return [{ source: "/verify/:token", headers: [
      { key: "Cache-Control", value: "no-store, private" },
      { key: "Referrer-Policy", value: "no-referrer" },
      { key: "X-Robots-Tag", value: "noindex, nofollow" },
    ] }];
  },
};

export default nextConfig;
