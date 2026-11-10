"use client";

import { useEffect, useState } from "react";

export function Chrome() {
  const [scrolled, setScrolled] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

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

  return (
    <header className={`chrome${scrolled ? " scrolled" : ""}`}>
      <a href="#" className="wordmark">
        VOVAGE<i>.</i>
      </a>
      <nav className="chrome-right">
        <span className="chrome-note mini">Estimates, not quotes</span>
        <button
          className="signin-btn"
          type="button"
          aria-label="Sign in to Vovage"
        >
          Sign in
        </button>
        <button
          className="theme-toggle"
          onClick={flip}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        >
          <span className="phase hollow" />
          <span className="knob" />
          <span className="phase" style={{ background: "var(--accent)" }} />
        </button>
      </nav>
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
