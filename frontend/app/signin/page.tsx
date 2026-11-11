"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  Alert,
  AuthShell,
  BusyButton,
  PasswordField,
} from "@/app/auth-shared";
import { setSession } from "@/lib/session";
import "./../auth.css";

export default function SignInPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [resetNote, setResetNote] = useState(false);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setOk(null);
    if (!email.trim() || !password) {
      setError("Enter your email and password to continue.");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setError("That doesn't look like a valid email address.");
      return;
    }
    setBusy(true);
    setTimeout(() => {
      const name = email
        .split("@")[0]
        .split(/[._-]/)[0]
        .replace(/^\w/, (c) => c.toUpperCase());
      setSession({ name: name || "Traveller", email: email.trim() });
      setOk("Signed in. Taking you to the search console…");
      setTimeout(() => router.push("/"), 700);
    }, 900);
  };

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
      <form className="auth-form" onSubmit={submit} noValidate>
        <h1 className="auth-title">
          Sign <em>in</em>
        </h1>
        <p className="auth-sub">Pick up right where you left off.</p>

        {error && <Alert kind="error">{error}</Alert>}
        {ok && <Alert kind="ok">{ok}</Alert>}

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

        <div className="auth-row">
          <label className="auth-check">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
            />
            <span>Remember me</span>
          </label>
          <button
            type="button"
            className="auth-forgot"
            onClick={() => setResetNote(true)}
          >
            Forgot password?
          </button>
        </div>
        {resetNote && (
          <p className="auth-note">
            Password reset goes live with our email verification rollout — we&rsquo;ll
            send a secure reset link to your registered address then.
          </p>
        )}

        <BusyButton
          busy={busy}
          label="Sign In"
          busyLabel="Signing In…"
        />

        <p className="auth-swap">
          New to Vovage? <Link href="/signup">Create an account</Link>
        </p>
      </form>
    </AuthShell>
  );
}
