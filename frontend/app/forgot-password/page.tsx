"use client";

import Link from "next/link";
import { useState } from "react";
import {
  Alert,
  AuthShell,
  BusyButton,
  authErrorMessage,
} from "@/app/auth-shared";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";
import "./../auth.css";

export default function ForgotPasswordPage() {
  const supabase = getSupabaseBrowserClient();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("That doesn't look like a valid email address.");
      return;
    }
    setBusy(true);
    try {
      const { error: err } = await supabase.auth.resetPasswordForEmail(
        email.trim(),
        {
          redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent("/auth/update-password")}`,
        },
      );
      if (err) {
        setError(authErrorMessage(err.message));
        return;
      }
      setSent(true);
    } catch {
      setError("Network problem reaching the auth service — try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell
      photo="https://images.unsplash.com/photo-1436491865332-7a61a109cc05?q=80&w=2400&auto=format&fit=crop"
      eyebrow="Account recovery"
      quote={
        <>
          Lost access? We&rsquo;ll guide you <em>home</em>.
        </>
      }
    >
      <form className="auth-form" onSubmit={submit} noValidate>
        <h1 className="auth-title">
          Reset <em>password</em>
        </h1>
        <p className="auth-sub">
          We&rsquo;ll email you a secure link to set a new password.
        </p>

        {error && <Alert kind="error">{error}</Alert>}
        {sent && (
          <Alert kind="ok">
            Reset link sent to <b>{email.trim()}</b> — open it on this device to
            set a new password.
          </Alert>
        )}

        {!sent && (
          <>
            <div className="auth-fields">
              <label className="field auth-field">
                <span className="cap mini">Email address</span>
                <input
                  className="control display"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  placeholder="you@example.com"
                  required
                />
              </label>
            </div>
            <BusyButton
              busy={busy}
              label="Send Reset Link"
              busyLabel="Sending…"
            />
          </>
        )}

        <p className="auth-swap">
          Remembered it? <Link href="/signin">Back to sign in</Link>
        </p>
      </form>
    </AuthShell>
  );
}
