import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Strict mode for catching issues early
  reactStrictMode: true,

  // Proxy API calls to FastAPI during development
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/:path*`,
      },
      // Lets the wake-up probe hit /health in local dev, where NEXT_PUBLIC_API_URL
      // is unset and requests are same-origin. In production the probe calls the
      // API's own origin directly and never reaches this rewrite.
      {
        source: "/health",
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/health`,
      },
    ];
  },

  // Security headers
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-DNS-Prefetch-Control", value: "on" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
