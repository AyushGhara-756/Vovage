import type { NextConfig } from "next";
import { config } from "dotenv";

config({ path: "../.env" });

function requireEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(
      `Missing required environment variable ${name}. Copy .env.example to .env and fill it in.`,
    );
  }
  return value;
}

const supabaseUrl = requireEnv("NEXT_PUBLIC_SUPABASE_URL");
requireEnv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY");

let supabaseOrigin: string;
try {
  supabaseOrigin = new URL(supabaseUrl).origin;
} catch {
  throw new Error("NEXT_PUBLIC_SUPABASE_URL must be a valid URL.");
}

const isProduction = process.env.NODE_ENV === "production";
if (isProduction && !supabaseOrigin.startsWith("https://")) {
  throw new Error("NEXT_PUBLIC_SUPABASE_URL must use https in production.");
}

const supabaseWsOrigin = supabaseOrigin.replace(/^https:/, "wss:");
const apiUrl = process.env.NEXT_PUBLIC_API_URL;
const apiOrigin = apiUrl ? new URL(apiUrl).origin : "";
const scriptSrc = ["'self'", "'unsafe-inline'"]
  .concat(isProduction ? [] : ["'unsafe-eval'"])
  .join(" ");
const connectSrc = ["'self'", supabaseOrigin, supabaseWsOrigin, apiOrigin]
  .filter(Boolean)
  .concat(isProduction ? [] : ["ws:", "wss:"])
  .join(" ");
const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src ${scriptSrc}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  `connect-src ${connectSrc}`,
  "frame-src 'self'",
  "frame-ancestors 'none'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
]
  .concat(isProduction ? ["upgrade-insecure-requests"] : [])
  .join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=()",
  },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
].concat(
  isProduction
    ? [
        {
          key: "Strict-Transport-Security",
          value: "max-age=63072000; includeSubDomains; preload",
        },
      ]
    : [],
);

const nextConfig: NextConfig = {
  devIndicators: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
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
