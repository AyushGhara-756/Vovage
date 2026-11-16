"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Alert,
  AuthShell,
  BusyButton,
  PasswordField,
  authErrorMessage,
} from "@/app/auth-shared";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";
import "./../../auth.css";

export default function UpdatePasswordPage() {
  const supabase = getSupabaseBrowserClient();
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(true);
  const [missingSession, setMissingSession] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setMissingSession(!data.session);
      setChecking(false);
    });
    return () => {
      active = false;
    };
  }, [supabase]);

  const strengthOk = (v: string) =>
    v.length >= 8 && /[a-zA-Z]/.test(v) && /[0-9]/.test(v);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!strengthOk(password)) {
      setError(
        "Password needs at least 8 characters including letters and numbers.",
      );
      return;
    }
    if (password.length > 72) {
      setError("Password is too long — use 72 characters or fewer.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords don't match — please retype the confirmation.");
      return;
    }
    setBusy(true);
    try {
      const { error: err } = await supabase.auth.updateUser({ password });
      if (err) {
        setError(authErrorMessage(err.message));
        return;
      }
      setDone(true);
      setTimeout(() => {
        router.push("/profile");
        router.refresh();
      }, 1200);
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
          A new key for your <em>next journey</em>.
        </>
      }
    >
      <form className="auth-form" onSubmit={submit} noValidate>
        <h1 className="auth-title">
          New <em>password</em>
        </h1>
        <p className="auth-sub">Choose a fresh password for your account.</p>

        {checking && <p className="auth-note">Checking your reset link…</p>}

        {!checking && missingSession && (
          <>
            <Alert kind="error">
              This reset link has expired, was already used, or was opened on a
              different device. Request a fresh link to continue.
            </Alert>
            <Link href="/forgot-password" className="launch-btn auth-btn">
              Request a new link
            </Link>
          </>
        )}

        {!checking && !missingSession && error && (
          <Alert kind="error">{error}</Alert>
        )}
        {!checking && !missingSession && done && (
          <Alert kind="ok">
            Password updated — taking you to your profile…
          </Alert>
        )}

        {!checking && !missingSession && !done && (
          <>
            <div className="auth-fields">
              <PasswordField
                cap="New password"
                value={password}
                onChange={setPassword}
                autoComplete="new-password"
                placeholder="At least 8 characters, letters + numbers"
              />
              <PasswordField
                cap="Confirm new password"
                value={confirm}
                onChange={setConfirm}
                autoComplete="new-password"
                placeholder="Repeat your password"
              />
            </div>
            <BusyButton busy={busy} label="Update Password" busyLabel="Updating…" />
          </>
        )}

        <p className="auth-swap">
          <Link href="/signin">Back to sign in</Link>
        </p>
      </form>
    </AuthShell>
  );
}
