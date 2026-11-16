"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { createSave } from "@/lib/account";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

type SearchType = "flight" | "hotel" | "package";

export function SaveSearchButton({
  searchType,
  params,
  defaultName,
}: {
  searchType: SearchType;
  params: Record<string, unknown>;
  defaultName: string;
}) {
  const supabase = getSupabaseBrowserClient();
  const pathname = usePathname();
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(defaultName);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const paramKey = JSON.stringify(params);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setReady(true);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) =>
      setSession(s),
    );
    return () => sub.subscription.unsubscribe();
  }, [supabase]);

  useEffect(() => {
    setName(defaultName);
    setOpen(false);
    setError(null);
    setSaved(false);
  }, [paramKey, defaultName]);

  useEffect(() => {
    if (!saved) return;
    const t = setTimeout(() => setSaved(false), 3200);
    return () => clearTimeout(t);
  }, [saved]);

  if (!ready) return null;

  if (!session) {
    return (
      <Link
        href={`/signin?next=${encodeURIComponent(pathname)}`}
        className="save-btn ghost"
      >
        Sign in to save
      </Link>
    );
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError("Give this search a name.");
      return;
    }
    setBusy(true);
    try {
      await createSave({
        search_type: searchType,
        search_name: name.trim(),
        search_params: params,
      });
      setSaved(true);
      setOpen(false);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not save this search.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="save-wrap">
      {saved ? (
        <span className="save-status" role="status">
          Saved ✓
        </span>
      ) : (
        <button
          type="button"
          className="save-btn"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
        >
          {open ? "Cancel" : "Save this search"}
        </button>
      )}
      {open && !saved && (
        <form className="save-form" onSubmit={submit}>
          <input
            className="save-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={80}
            placeholder="Name this search"
            aria-label="Saved search name"
            autoFocus
          />
          <button className="save-btn solid" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </button>
        </form>
      )}
      {error && (
        <span className="save-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
