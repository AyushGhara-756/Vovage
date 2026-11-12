import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";
import type { EmailOtpType } from "@supabase/supabase-js";
import { safeNextPath } from "@/lib/safe-next";

const OTP_TYPES = new Set<EmailOtpType>([
  "signup",
  "invite",
  "magiclink",
  "recovery",
  "email_change",
  "email",
]);

function failure(origin: string, message: string) {
  return NextResponse.redirect(
    `${origin}/signin?verify_error=${encodeURIComponent(message)}`,
  );
}

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const tokenHash = searchParams.get("token_hash");
  const otpType = searchParams.get("type") as EmailOtpType | null;
  const error = searchParams.get("error") || searchParams.get("error_code");
  const errorDescription = searchParams.get("error_description");
  const next = safeNextPath(searchParams.get("next"));

  if (error) {
    return failure(
      origin,
      errorDescription || error || "Verification failed",
    );
  }

  if (!code && !(tokenHash && otpType && OTP_TYPES.has(otpType))) {
    return failure(origin, "This link is missing its verification token.");
  }

  const destination = new URL(next, origin);
  const isRecovery =
    otpType === "recovery" ||
    destination.pathname === "/auth/update-password";
  if (!isRecovery) destination.searchParams.set("verified", "1");
  const redirectTo = `${origin}${destination.pathname}${destination.search}`;

  let response = NextResponse.redirect(redirectTo);

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          response = NextResponse.redirect(redirectTo);
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  try {
    const result = code
      ? await supabase.auth.exchangeCodeForSession(code)
      : await supabase.auth.verifyOtp({
          type: otpType as EmailOtpType,
          token_hash: tokenHash as string,
        });

    if (result.error) {
      return failure(origin, result.error.message);
    }
  } catch {
    return failure(
      origin,
      "Verification link is invalid or expired — request a new one.",
    );
  }

  return response;
}
