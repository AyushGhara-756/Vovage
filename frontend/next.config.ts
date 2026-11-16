import type { NextConfig } from "next";
import { config } from "dotenv";

config({ path: "../.env" });

const nextConfig: NextConfig = {
  devIndicators: false,
  async rewrites() {
    // Same-origin proxy: the Flask prediction API on :6050
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:6050/api/:path*",
      },
    ];
  },
};

export default nextConfig;
