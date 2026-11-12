"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useEffect,
  useRef,
  useState,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";
import { searchAirports, type AirportHit } from "@/lib/api";
import { verificationResendOptions } from "@/lib/auth-redirect";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

export function AuthShell({
  photo,
  eyebrow,
  quote,
  children,
}: {
  photo?: string;
  eyebrow: string;
  quote: ReactNode;
  children: ReactNode;
}) {
  return (
    <main className="auth">
      <div className="auth-form-pane">
        <header className="auth-head">
          <Link href="/" className="wordmark" aria-label="Vovage home">
            VOVAGE<i>.</i>
          </Link>
          <Link href="/" className="auth-back">
            ← Back to search
          </Link>
        </header>
        {children}
        <p className="auth-legal">
          © {new Date().getFullYear()} Vovage · Prices are estimates, not
          offers.
        </p>
      </div>
      <aside className="auth-visual" style={photo ? ({ "--auth-photo": `url(${photo})` } as React.CSSProperties) : undefined} aria-hidden>
        <div className="auth-quote">
          <span className="cap mini">{eyebrow}</span>
          <h2>{quote}</h2>
        </div>
      </aside>
    </main>
  );
}

export function PasswordField({
  cap,
  value,
  onChange,
  autoComplete,
  placeholder,
}: {
  cap: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: InputHTMLAttributes<HTMLInputElement>["autoComplete"];
  placeholder?: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <label className="field auth-field has-toggle">
      <span className="cap mini">{cap}</span>
      <input
        className="control display"
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        placeholder={placeholder}
        required
      />
      <button
        type="button"
        className="auth-toggle"
        aria-label={show ? "Hide password" : "Show password"}
        aria-pressed={show}
        onClick={() => setShow((s) => !s)}
      >
        {show ? "Hide" : "Show"}
      </button>
    </label>
  );
}

export function AirportField({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<AirportHit[]>([]);
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLLabelElement>(null);

  useEffect(() => {
    if (query.trim().length < 2) {
      setHits([]);
      return;
    }
    const t = setTimeout(() => {
      searchAirports(query.trim())
        .then((r) => {
          setHits(r.results);
          setOpen(true);
        })
        .catch(() => setHits([]));
    }, 220);
    return () => clearTimeout(t);
  }, [query]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const display = value || query;

  return (
    <label className="field auth-field ac" ref={boxRef}>
      <span className="cap mini">
        Home airport
        <i>optional</i>
      </span>
      <input
        className="control display"
        value={display}
        placeholder="e.g. BOM — Mumbai"
        onChange={(e) => {
          setQuery(e.target.value);
          onChange("");
        }}
        onFocus={() => hits.length && setOpen(true)}
      />
      {open && hits.length > 0 && (
        <div className="auth-ac" role="listbox">
          {hits.map((h) => (
            <button
              key={h.code}
              type="button"
              role="option"
              aria-selected={false}
              onClick={() => {
                onChange(`${h.code} — ${h.city}, ${h.country}`);
                setQuery("");
                setOpen(false);
              }}
            >
              <span className="code">{h.code}</span>
              <span className="place">
                {h.name} <span className="dim">· {h.city}, {h.country}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </label>
  );
}

export function normalizeCity(value: string, options: string[] = []) {
  const clean = value.trim().replace(/\s+/g, " ");
  if (!clean) return "";
  const match = options.find((c) => c.toLowerCase() === clean.toLowerCase());
  if (match) return match;
  return clean.replace(/\b[a-z]/g, (c) => c.toUpperCase());
}

export function CityField({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLLabelElement>(null);

  const q = value.trim().toLowerCase();
  const hits = options.filter(
    (c) => !q || c.toLowerCase().includes(q),
  );

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <label className="field auth-field ac select" ref={boxRef}>
      <span className="cap mini">
        Home city
        <i>optional</i>
      </span>
      <input
        className="control display"
        value={value}
        placeholder="e.g. Mumbai"
        autoComplete="address-level2"
        autoCapitalize="words"
        autoCorrect="on"
        spellCheck
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => {
          const next = normalizeCity(value, options);
          if (next !== value) onChange(next);
          setOpen(false);
        }}
      />
      {open && hits.length > 0 && (
        <div className="auth-ac" role="listbox">
          {hits.map((c) => (
            <button
              key={c}
              type="button"
              role="option"
              aria-selected={c === value}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                onChange(c);
                setOpen(false);
              }}
            >
              <span className="place">{c}</span>
            </button>
          ))}
        </div>
      )}
    </label>
  );
}

export function Alert({
  kind,
  children,
}: {
  kind: "error" | "ok";
  children: ReactNode;
}) {
  return (
    <div className={`auth-alert${kind === "ok" ? " ok" : ""}`} role={kind === "error" ? "alert" : "status"}>
      <b>{kind === "ok" ? "✓" : "!"}</b>
      <span>{children}</span>
    </div>
  );
}

export function BusyButton({
  busy,
  label,
  busyLabel,
}: {
  busy: boolean;
  label: string;
  busyLabel: string;
}) {
  return (
    <button
      type="submit"
      className={`launch-btn auth-btn${busy ? " busy" : ""}`}
      disabled={busy}
    >
      {busy ? busyLabel : label}
    </button>
  );
}

export function VerifyPending({
  email,
  onBack,
}: {
  email: string;
  onBack: () => void;
}) {
  const supabase = getSupabaseBrowserClient();
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const resend = async () => {
    setBusy(true);
    setNote(null);
    const { error } = await supabase.auth.resend(
      verificationResendOptions(email, window.location.origin),
    );
    setNote(
      error
        ? "Couldn't resend just now — please wait a minute and try again."
        : "Verification link sent again. Check your inbox (and spam).",
    );
    setBusy(false);
  };

  return (
    <>
      <Alert kind="ok">
        Account created. Supabase has emailed a verification link to{" "}
        <b>{email}</b> — open it on this device to finish signing in.
      </Alert>
      {note && <p className="auth-note">{note}</p>}
      <div className="auth-row" style={{ paddingTop: 14 }}>
        <button
          type="button"
          className="auth-forgot"
          onClick={resend}
          disabled={busy}
        >
          {busy ? "Resending…" : "Resend verification email"}
        </button>
        <button type="button" className="auth-forgot" onClick={onBack}>
          Back to form
        </button>
      </div>
    </>
  );
}

export { authErrorMessage, verifyErrorMessage } from "@/lib/auth-errors";
export { safeNextPath } from "@/lib/safe-next";
