"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import {
  Alert,
  AirportField,
  authErrorMessage,
  AuthShell,
  BusyButton,
  CityField,
  normalizeCity,
  PasswordField,
  safeNextPath,
  VerifyPending,
} from "@/app/auth-shared";
import { authCallbackUrl } from "@/lib/auth-redirect";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";
import "./../auth.css";

const CITIES = [
  "Delhi",
  "Mumbai",
  "Bangalore",
  "Kolkata",
  "Chennai",
  "Hyderabad",
];

const CURRENCIES = ["INR", "USD", "EUR", "GBP", "AED"];

const TERMS_VERSION = "v1.0";
const PRIVACY_VERSION = "v1.0";

function SignUpForm() {
  const router = useRouter();
  const params = useSearchParams();
  const supabase = getSupabaseBrowserClient();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [phone, setPhone] = useState("");
  const [city, setCity] = useState("");
  const [airport, setAirport] = useState("");
  const [currency, setCurrency] = useState("INR");
  const [terms, setTerms] = useState(false);
  const [privacy, setPrivacy] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingEmail, setPendingEmail] = useState<string | null>(null);

  const next = safeNextPath(params.get("next"));

  const strengthOk = (v: string) =>
    v.length >= 8 && /[a-zA-Z]/.test(v) && /[0-9]/.test(v);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (name.trim().length < 2)
      return setError("Please enter your full name (at least 2 characters).");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()))
      return setError("That doesn't look like a valid email address.");
    const normalizedPhone = phone.trim().replace(/[\s()-]/g, "");
    if (normalizedPhone && !/^\+[1-9]\d{7,14}$/.test(normalizedPhone))
      return setError(
        "Phone must include country code and only digits, e.g. +919876543210.",
      );
    if (!strengthOk(password))
      return setError(
        "Password needs at least 8 characters including letters and numbers.",
      );
    if (password.length > 72)
      return setError("Password is too long — use 72 characters or fewer.");
    if (password !== confirm)
      return setError("Passwords don't match — please retype the confirmation.");
    if (!terms) return setError("Please accept the Terms & Conditions.");
    if (!privacy) return setError("Please accept the Privacy Policy.");

    setBusy(true);
    try {
      const { data, error: err } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: {
          emailRedirectTo: authCallbackUrl(window.location.origin, next),
          data: {
            full_name: name.trim(),
            phone_number: normalizedPhone || null,
            home_city: normalizeCity(city, CITIES) || null,
            home_airport: airport || null,
            preferred_currency: currency || "INR",
            terms_accepted: true,
            terms_version: TERMS_VERSION,
            privacy_version: PRIVACY_VERSION,
          },
        },
      });
      if (err) {
        setError(authErrorMessage(err.message));
        return;
      }
      if (data.user && (data.user.identities?.length ?? 0) === 0) {
        setError(
          "An account with this email already exists — try signing in instead.",
        );
        return;
      }
      if (!data.session && data.user) {
        setPendingEmail(email.trim());
        return;
      }
      router.push(next);
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
        <p className="auth-sub">One click left to activate your account.</p>
        <VerifyPending
          email={pendingEmail}
          onBack={() => setPendingEmail(null)}
        />
        <p className="auth-swap">
          Already verified? <Link href="/signin">Sign in</Link>
        </p>
      </form>
    );
  }

  return (
    <form className="auth-form" onSubmit={submit} noValidate>
      <h1 className="auth-title">
        Create <em>account</em>
      </h1>
      <p className="auth-sub">
        One account for fares, stays and curated packages.
      </p>

      {error && <Alert kind="error">{error}</Alert>}

      <div className="auth-fields">
        <label className="field auth-field">
          <span className="cap mini">Full name</span>
          <input
            className="control display"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="name"
            placeholder="Your name"
            required
          />
        </label>
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
          autoComplete="new-password"
          placeholder="At least 8 characters, letters + numbers"
        />
        <PasswordField
          cap="Confirm password"
          value={confirm}
          onChange={setConfirm}
          autoComplete="new-password"
          placeholder="Repeat your password"
        />
        <div className="auth-grid">
          <label className="field auth-field">
            <span className="cap mini">
              Phone
              <i>optional</i>
            </span>
            <input
              className="control display"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              autoComplete="tel"
              placeholder="+91"
            />
          </label>
          <label className="field auth-field select">
            <span className="cap mini">
              Currency
              <i>default</i>
            </span>
            <select
              className="control display"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="auth-grid">
          <CityField value={city} onChange={setCity} options={CITIES} />
          <AirportField value={airport} onChange={setAirport} />
        </div>
      </div>

      <label className="auth-check">
        <input
          type="checkbox"
          checked={terms}
          onChange={(e) => setTerms(e.target.checked)}
          required
        />
        <span>
          I agree to the <Link href="/">Terms &amp; Conditions</Link> ({TERMS_VERSION})
        </span>
      </label>
      <label className="auth-check">
        <input
          type="checkbox"
          checked={privacy}
          onChange={(e) => setPrivacy(e.target.checked)}
          required
        />
        <span>
          I consent to the <Link href="/">Privacy Policy</Link> ({PRIVACY_VERSION}){" "}
          and the use of my details for personalised fare insights
        </span>
      </label>

      <BusyButton busy={busy} label="Create Account" busyLabel="Creating Account…" />

      <p className="auth-swap">
        Already with us? <Link href="/signin">Sign in</Link>
      </p>
    </form>
  );
}

export default function SignUpPage() {
  return (
    <AuthShell
      photo="https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=2400&auto=format&fit=crop"
      eyebrow="Begin the journey"
      quote={
        <>
          Every great trip starts with a single <em>decision</em>.
        </>
      }
    >
      <Suspense
        fallback={
          <form className="auth-form">
            <h1 className="auth-title">
              Create <em>account</em>
            </h1>
          </form>
        }
      >
        <SignUpForm />
      </Suspense>
    </AuthShell>
  );
}
