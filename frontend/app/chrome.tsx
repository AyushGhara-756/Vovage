"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  clearSession,
  getSession,
  onSessionChange,
  type VovageSession,
} from "@/lib/session";

export function Chrome() {
  const [scrolled, setScrolled] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [toast, setToast] = useState<string | null>(null);
  const [session, setSessionState] = useState<VovageSession | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmingOut, setConfirmingOut] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    setScrolled(window.scrollY > 24);
    const onScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const current = document.documentElement.dataset.theme;
    if (current === "light" || current === "dark") setTheme(current);
  }, []);

  useEffect(() => {
    const sync = () => {
      setSessionState(getSession());
      setMenuOpen(false);
      setConfirmingOut(false);
    };
    sync();
    return onSessionChange(sync);
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3200);
    return () => clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) {
        setMenuOpen(false);
        setConfirmingOut(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMenuOpen(false);
        setConfirmingOut(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const flip = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("vovage-theme", next);
    } catch {
      /* private mode */
    }
    setTheme(next);
  };

  const signOut = () => {
    clearSession();
    setMenuOpen(false);
    setConfirmingOut(false);
    router.push("/signin");
  };

  const initial = session?.name?.trim()?.[0]?.toUpperCase() ?? "";

  return (
    <header className={`chrome${scrolled ? " scrolled" : ""}`}>
      <Link href="/" className="wordmark" aria-label="Vovage home">
        VOVAGE<i>.</i>
      </Link>
      <nav className="chrome-right">
        <span className="chrome-note mini">Estimates, not quotes</span>
        {session ? (
          <div className="acct-wrap" ref={menuRef}>
            <button
              className="acct-btn"
              type="button"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label="Account menu"
              onClick={() => setMenuOpen((o) => !o)}
            >
              <span className="acct-avatar">{initial}</span>
              <span className="acct-name">{session.name}</span>
            </button>
            {menuOpen && (
              <div className="acct-menu" role="menu">
                <div className="acct-id">
                  <b>{session.name}</b>
                  <span>{session.email}</span>
                </div>
                {confirmingOut ? (
                  <div className="acct-confirm">
                    <p>Sign out of Vovage?</p>
                    <div className="acct-confirm-actions">
                      <button
                        type="button"
                        className="no"
                        onClick={() => setConfirmingOut(false)}
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        className="yes"
                        role="menuitem"
                        onClick={signOut}
                      >
                        Sign Out
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="acct-item danger"
                    role="menuitem"
                    onClick={() => setConfirmingOut(true)}
                  >
                    Sign Out
                  </button>
                )}
              </div>
            )}
          </div>
        ) : (
          <Link
            href="/signin"
            className="signin-btn"
            aria-label="Sign in to Vovage"
          >
            Sign in
          </Link>
        )}
        <button
          className="theme-toggle"
          onClick={flip}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          aria-pressed={theme === "light"}
        >
          <span className="phase hollow" />
          <span className="knob" />
          <span className="phase" style={{ background: "var(--accent)" }} />
        </button>
      </nav>
      {toast && (
        <div className="toast display" role="status" aria-live="polite">
          {toast}
        </div>
      )}
    </header>
  );
}

export function Ticker({ items }: { items: string[][] }) {
  const cells = [...items, ...items]; // loop seam
  return (
    <div className="ticker" aria-hidden>
      <div className="ticker-track">
        {cells.map(([from, to, price, meta], i) => (
          <span key={i} className="ticker-cell">
            <span className="route">
              {from} <i>→</i> {to}
            </span>
            <b>₹{price}</b>
            <span>{meta}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
