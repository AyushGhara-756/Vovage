import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
