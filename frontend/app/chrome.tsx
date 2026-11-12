"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";
import type { Session } from "@supabase/supabase-js";

export function Chrome() {
  const [scrolled, setScrolled] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [toast, setToast] = useState<string | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [profileName, setProfileName] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmingOut, setConfirmingOut] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const supabase = getSupabaseBrowserClient();

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
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      setSession(s);
      setMenuOpen(false);
      setConfirmingOut(false);
    });
    return () => sub.subscription.unsubscribe();
  }, [supabase]);

  useEffect(() => {
    if (!session?.user) {
      setProfileName(null);
      return;
    }
    const meta = session.user.user_metadata as { full_name?: string } | null;
    setProfileName(meta?.full_name ?? null);
    supabase
      .from("profiles")
      .select("full_name")
      .eq("id", session.user.id)
      .single()
      .then(({ data }) => {
        if (data?.full_name) setProfileName(data.full_name);
      });
  }, [session, supabase]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3200);
    return () => clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get("verified") === "1") {
      setToast("Email verified — welcome aboard.");
      url.searchParams.delete("verified");
      window.history.replaceState(
        {},
        "",
        `${url.pathname}${url.search}${url.hash}`,
      );
    }
  }, []);

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

  const signOut = async () => {
    await supabase.auth.signOut({ scope: "local" });
    setMenuOpen(false);
    setConfirmingOut(false);
    router.push("/signin");
    router.refresh();
  };

  const initial =
    (profileName ?? session?.user?.email ?? "V").trim()[0]?.toUpperCase() ?? "V";

  return (
    <header className={`chrome${scrolled ? " scrolled" : ""}`}>
      <Link href="/" className="wordmark" aria-label="Vovage home">
        VOVAGE<i>.</i>
      </Link>
      <nav className="chrome-right">
        <span className="chrome-note mini">Estimates, not quotes</span>
        {session?.user ? (
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
              <span className="acct-name">{profileName ?? "Account"}</span>
            </button>
            {menuOpen && (
              <div className="acct-menu" role="menu">
                <div className="acct-id">
                  <b>{profileName ?? "Traveller"}</b>
                  <span>{session.user.email}</span>
                </div>
                <Link href="/profile" className="acct-item" role="menuitem">
                  Profile &amp; saved searches
                </Link>
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
