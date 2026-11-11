"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  Alert,
  AirportField,
  AuthShell,
  BusyButton,
  PasswordField,
} from "@/app/auth-shared";
import { setSession } from "@/lib/session";
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

export default function SignUpPage() {
  const router = useRouter();
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
  const [ok, setOk] = useState<string | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setOk(null);

    if (!name.trim()) return setError("Please tell us your full name.");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()))
      return setError("That doesn't look like a valid email address.");
    if (password.length < 8)
      return setError("Use at least 8 characters for your password.");
    if (password !== confirm)
      return setError("Passwords don't match — please retype the confirmation.");
    if (!terms) return setError("Please accept the Terms & Conditions.");
    if (!privacy) return setError("Please accept the Privacy Policy.");

    setBusy(true);
    setTimeout(() => {
      setSession({ name: name.trim(), email: email.trim() });
      setOk("Account created. Taking you to the search console…");
      setTimeout(() => router.push("/"), 700);
    }, 1100);
  };

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
      <form className="auth-form" onSubmit={submit} noValidate>
        <h1 className="auth-title">
          Create <em>account</em>
        </h1>
        <p className="auth-sub">
          One account for fares, stays and curated packages.
        </p>

        {error && <Alert kind="error">{error}</Alert>}
        {ok && <Alert kind="ok">{ok}</Alert>}

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
            placeholder="At least 8 characters"
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
            <label className="field auth-field select">
              <span className="cap mini">
                Home city
                <i>optional</i>
              </span>
              <select
                className="control display"
                value={city}
                onChange={(e) => setCity(e.target.value)}
              >
                <option value="">Select city</option>
                {CITIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
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
            I agree to the <Link href="/">Terms &amp; Conditions</Link>
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
            I consent to the <Link href="/">Privacy Policy</Link> and the use of
            my details for personalised fare insights
          </span>
        </label>

        <BusyButton
          busy={busy}
          label="Create Account"
          busyLabel="Creating Account…"
        />

        <p className="auth-swap">
          Already with us? <Link href="/signin">Sign in</Link>
        </p>
      </form>
    </AuthShell>
  );
}
