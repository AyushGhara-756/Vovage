export function authCallbackUrl(origin: string, next = "/"): string {
  const url = new URL("/auth/callback", origin);
  url.searchParams.set("next", next);
  return url.toString();
}

export function verificationResendOptions(email: string, origin: string) {
  return {
    type: "signup" as const,
    email,
    options: { emailRedirectTo: authCallbackUrl(origin, "/profile") },
  };
}
