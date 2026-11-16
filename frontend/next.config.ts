import type { NextConfig } from "next";
import { config } from "dotenv";

config({ path: "../.env" });

const nextConfig: NextConfig = {
  devIndicators: false,
  async rewrites() {
    // Same-origin proxy: the Flask prediction API on :6050.
    // Dev-only — on Vercel, /api/* is routed to the backend service by the
    // platform before it ever reaches the Next.js app.
    if (process.env.NODE_ENV === "production") return [];
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:6050/api/:path*",
      },
    ];
  },
};

export default nextConfig;
