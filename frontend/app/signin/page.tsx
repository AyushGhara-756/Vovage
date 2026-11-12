"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import {
  Alert,
  authErrorMessage,
  AuthShell,
  BusyButton,
  PasswordField,
  safeNextPath,
  VerifyPending,
  verifyErrorMessage,
} from "@/app/auth-shared";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";
import "./../auth.css";

function SignInForm() {
  const router = useRouter();
  const params = useSearchParams();
  const supabase = getSupabaseBrowserClient();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingEmail, setPendingEmail] = useState<string | null>(null);

  const next = safeNextPath(params.get("next"));
  const verifyError = params.get("verify_error");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !password) {
      setError("Enter your email and password to continue.");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("That doesn't look like a valid email address.");
      return;
    }
    setBusy(true);
    try {
      const { data, error: err } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });
      if (err) {
        if (
          err.message.toLowerCase().includes("not confirmed") &&
          email.trim()
        ) {
          setPendingEmail(email.trim());
          return;
        }
        setError(authErrorMessage(err.message));
        return;
      }
      if (data.session) {
        router.push(next);
      }
    } catch {
      setError("Network problem reaching the auth service — try again.");
    } finally {
      setBusy(false);
    }
  };

  if (pendingEmail) {
    return (
      <form className="auth-form" onSubmit={(e) => e.preventDefault()}>
        <h1 className="auth-title">
          Verify <em>email</em>
        </h1>
        <p className="auth-sub">
          Your account exists but the address isn&rsquo;t verified yet.
        </p>
        <VerifyPending
          email={pendingEmail}
          onBack={() => setPendingEmail(null)}
        />
        <p className="auth-swap">
          Verified already? <Link href="/signin">Try again</Link>
        </p>
      </form>
    );
  }

  return (
    <form className="auth-form" onSubmit={submit} noValidate>
      <h1 className="auth-title">
        Sign <em>in</em>
      </h1>
      <p className="auth-sub">Pick up right where you left off.</p>

      {verifyError && (
        <Alert kind="error">{verifyErrorMessage(verifyError)}</Alert>
      )}
      {error && <Alert kind="error">{error}</Alert>}

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
        <PasswordField
          cap="Password"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
          placeholder="Your password"
        />
      </div>

      <div className="auth-row" style={{ justifyContent: "flex-end" }}>
        <Link href="/forgot-password" className="auth-forgot">
          Forgot password?
        </Link>
      </div>

      <BusyButton busy={busy} label="Sign In" busyLabel="Signing In…" />

      <p className="auth-swap">
        New to Vovage? <Link href="/signup">Create an account</Link>
      </p>
    </form>
  );
}

export default function SignInPage() {
  return (
    <AuthShell
      photo="https://images.unsplash.com/photo-1436491865332-7a61a109cc05?q=80&w=2400&auto=format&fit=crop"
      eyebrow="Welcome back"
      quote={
        <>
          Your next <em>journey</em> is already boarding.
        </>
      }
    >
      <Suspense
        fallback={
          <form className="auth-form">
            <h1 className="auth-title">
              Sign <em>in</em>
            </h1>
          </form>
        }
      >
        <SignInForm />
      </Suspense>
    </AuthShell>
  );
}
