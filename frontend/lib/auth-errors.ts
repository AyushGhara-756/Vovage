export function authErrorMessage(error: string): string {
  const e = error.toLowerCase();
  if (e.includes("already registered") || e.includes("already exists"))
    return "An account with this email already exists — try signing in instead.";
  if (e.includes("rate limit") || e.includes("too many"))
    return "Too many attempts — wait a minute and try again.";
  if (e.includes("invalid login") || e.includes("invalid credentials"))
    return "Incorrect email or password.";
  if (e.includes("email not confirmed") || e.includes("not confirmed"))
    return "Your email isn't verified yet — check your inbox for the verification link.";
  if (e.includes("password should be at least") || e.includes("weak"))
    return "Password is too weak — use at least 8 characters with letters and numbers.";
  if (e.includes("should be different"))
    return "Choose a password you haven't used for this account before.";
  if (e.includes("expired") || e.includes("otp_expired"))
    return "That link has expired — request a fresh email and try again.";
  if (e.includes("invalid token") || e.includes("token has expired"))
    return "That link is invalid or has already been used — request a new one.";
  if (e.includes("session missing") || e.includes("auth session missing"))
    return "Your reset session has expired — request a new password reset email.";
  if (e.includes("network") || e.includes("fetch"))
    return "Network problem reaching the auth service — check your connection.";
  return error;
}

export function verifyErrorMessage(raw: string): string {
  const e = raw.toLowerCase();
  if (e.includes("pkce") || e.includes("code verifier") || e.includes("verifier"))
    return "Open this link in the same browser you requested it from, or request a new email below.";
  if (e.includes("expired") || e.includes("otp_expired"))
    return "That verification link has expired. Sign in below and request a new email.";
  if (
    e.includes("invalid") ||
    e.includes("missing") ||
    e.includes("token") ||
    e.includes("used")
  )
    return "That verification link is invalid or already used. Request a fresh one from the sign-in screen.";
  return authErrorMessage(raw);
}
