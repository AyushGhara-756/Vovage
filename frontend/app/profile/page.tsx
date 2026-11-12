"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Chrome } from "@/app/chrome";
import { AirportField } from "@/app/auth-shared";
import { verificationResendOptions } from "@/lib/auth-redirect";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";
import {
  clearHistory,
  deleteHistory,
  deleteSave,
  fetchAccount,
  listHistory,
  listSaves,
  updateAccount,
  updateSave,
  uploadAvatar,
  type AccountPayload,
  type HistoryEntry,
  type SavedSearch,
} from "@/lib/account";
import "./profile.css";
import "../auth.css";

const CURRENCIES = ["INR", "USD", "EUR", "GBP", "AED"];
const TRAVEL_TYPES = ["leisure", "business", "adventure", "family"];
const CABINS = ["economy", "premium_economy", "business", "first"];
const RATINGS = [0, 1, 2, 3, 4, 5];

type ProfileForm = {
  full_name: string;
  phone_number: string;
  home_city: string;
  home_airport: string;
  preferred_currency: string;
};

type PrefForm = {
  preferred_travel_type: string;
  preferred_cabin: string;
  preferred_hotel_rating: number;
  notification_enabled: boolean;
};

const EMPTY_PROFILE: ProfileForm = {
  full_name: "",
  phone_number: "",
  home_city: "",
  home_airport: "",
  preferred_currency: "INR",
};

const EMPTY_PREFS: PrefForm = {
  preferred_travel_type: "",
  preferred_cabin: "",
  preferred_hotel_rating: 0,
  notification_enabled: true,
};

function message(e: unknown): string {
  return e instanceof Error ? e.message : "Something went wrong — try again.";
}

function when(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function summarize(params: Record<string, unknown>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .slice(0, 4)
    .map(([k, v]) => `${k.replaceAll("_", " ")}: ${String(v)}`);
  return parts.length ? parts.join(" · ") : "No parameters stored";
}

function prettyType(type: string): string {
  return type.charAt(0).toUpperCase() + type.slice(1);
}

export default function ProfilePage() {
  const supabase = getSupabaseBrowserClient();
  const avatarInput = useRef<HTMLInputElement>(null);

  const [account, setAccount] = useState<AccountPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [resending, setResending] = useState(false);

  const [form, setForm] = useState<ProfileForm>(EMPTY_PROFILE);
  const [prefs, setPrefs] = useState<PrefForm>(EMPTY_PREFS);

  const [saves, setSaves] = useState<SavedSearch[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [listsError, setListsError] = useState<string | null>(null);
  const [rowBusy, setRowBusy] = useState<string | null>(null);
  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const applyAccount = (data: AccountPayload) => {
    setAccount(data);
    setForm({
      full_name: data.profile?.full_name ?? "",
      phone_number: data.profile?.phone_number ?? "",
      home_city: data.profile?.home_city ?? "",
      home_airport: data.profile?.home_airport ?? "",
      preferred_currency: data.profile?.preferred_currency ?? "INR",
    });
    setPrefs({
      preferred_travel_type: data.preferences?.preferred_travel_type ?? "",
      preferred_cabin: data.preferences?.preferred_cabin ?? "",
      preferred_hotel_rating: data.preferences?.preferred_hotel_rating ?? 0,
      notification_enabled: data.preferences?.notification_enabled ?? true,
    });
  };

  const load = async () => {
    setLoading(true);
    setLoadError(null);
    setListsError(null);
    try {
      const data = await fetchAccount();
      applyAccount(data);
    } catch (e) {
      setLoadError(message(e));
      setLoading(false);
      return;
    }

    const [savesResult, historyResult] = await Promise.allSettled([
      listSaves(),
      listHistory(),
    ]);
    if (savesResult.status === "fulfilled") setSaves(savesResult.value.saves);
    if (historyResult.status === "fulfilled")
      setHistory(historyResult.value.history);
    if (
      savesResult.status === "rejected" ||
      historyResult.status === "rejected"
    ) {
      setListsError(
        message(
          savesResult.status === "rejected"
            ? savesResult.reason
            : (historyResult as PromiseRejectedResult).reason,
        ),
      );
    }
    setLoading(false);
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const flash = (text: string) => {
    setNotice(text);
    setError(null);
  };

  const fail = (e: unknown) => {
    setError(message(e));
    setNotice(null);
  };

  const patchForm = (kv: Partial<ProfileForm>) =>
    setForm((f) => ({ ...f, ...kv }));
  const patchPrefs = (kv: Partial<PrefForm>) =>
    setPrefs((p) => ({ ...p, ...kv }));

  const saveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    if (form.full_name.trim().length < 2) {
      setError("Full name must be at least 2 characters.");
      return;
    }
    const normalizedPhone = form.phone_number.trim().replace(/[\s()-]/g, "");
    if (normalizedPhone && !/^\+[1-9]\d{7,14}$/.test(normalizedPhone)) {
      setError(
        "Phone must include country code and only digits, e.g. +919876543210.",
      );
      return;
    }
    setSavingProfile(true);
    try {
      const data = await updateAccount({
        full_name: form.full_name.trim(),
        phone_number: normalizedPhone,
        home_city: form.home_city.trim(),
        home_airport: form.home_airport.trim(),
        preferred_currency: form.preferred_currency,
      });
      applyAccount(data);
      flash("Profile updated.");
    } catch (err) {
      fail(err);
    } finally {
      setSavingProfile(false);
    }
  };

  const savePrefs = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setSavingPrefs(true);
    try {
      const data = await updateAccount({
        preferred_travel_type: prefs.preferred_travel_type,
        preferred_cabin: prefs.preferred_cabin,
        preferred_hotel_rating: Number(prefs.preferred_hotel_rating),
        notification_enabled: prefs.notification_enabled,
      });
      applyAccount(data);
      flash("Travel preferences saved.");
    } catch (err) {
      fail(err);
    } finally {
      setSavingPrefs(false);
    }
  };

  const chooseAvatar = () => avatarInput.current?.click();

  const onAvatarFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError(null);
    setNotice(null);
    setUploading(true);
    try {
      const url = await uploadAvatar(file);
      const data = await updateAccount({ avatar_url: url });
      applyAccount(data);
      flash("Avatar updated.");
    } catch (err) {
      fail(err);
    } finally {
      setUploading(false);
    }
  };

  const resendVerification = async () => {
    if (!account?.email) return;
    setResending(true);
    setError(null);
    setNotice(null);
    const { error: err } = await supabase.auth.resend(
      verificationResendOptions(account.email, window.location.origin),
    );
    if (err) fail(err);
    else flash("Verification email sent again — check your inbox.");
    setResending(false);
  };

  const beginRename = (save: SavedSearch) => {
    setRenameId(save.id);
    setRenameValue(save.search_name);
  };

  const commitRename = async (id: string) => {
    setRowBusy(id);
    setError(null);
    setNotice(null);
    try {
      const { save } = await updateSave(id, {
        search_name: renameValue.trim() || "Untitled search",
      });
      setSaves((rows) => rows.map((r) => (r.id === save.id ? save : r)));
      setRenameId(null);
      flash("Saved search renamed.");
    } catch (err) {
      fail(err);
    } finally {
      setRowBusy(null);
    }
  };

  const removeSave = async (save: SavedSearch) => {
    if (!window.confirm(`Delete “${save.search_name}”?`)) return;
    setRowBusy(save.id);
    setError(null);
    setNotice(null);
    try {
      await deleteSave(save.id);
      setSaves((rows) => rows.filter((r) => r.id !== save.id));
      flash("Saved search deleted.");
    } catch (err) {
      fail(err);
    } finally {
      setRowBusy(null);
    }
  };

  const removeHistory = async (entry: HistoryEntry) => {
    setRowBusy(entry.id);
    setError(null);
    setNotice(null);
    try {
      await deleteHistory(entry.id);
      setHistory((rows) => rows.filter((r) => r.id !== entry.id));
      flash("History entry deleted.");
    } catch (err) {
      fail(err);
    } finally {
      setRowBusy(null);
    }
  };

  const clearAllHistory = async () => {
    if (!history.length || !window.confirm("Clear your entire search history?"))
      return;
    setRowBusy("history-all");
    setError(null);
    setNotice(null);
    try {
      await clearHistory();
      setHistory([]);
      flash("Search history cleared.");
    } catch (err) {
      fail(err);
    } finally {
      setRowBusy(null);
    }
  };

  const identity = account?.profile?.full_name || account?.email || "Traveller";
  const initial = identity.trim().charAt(0).toUpperCase() || "V";
  const avatarUrl = account?.profile?.avatar_url;

  return (
    <div className="profile-page">
      <Chrome />
      <main className="profile">
        <header className="profile-head">
          <div className="profile-eyebrow">
            <span className="rule" />
            <span className="mini">Your account</span>
          </div>
          <h1 className="profile-title">
            Traveller <em>profile</em>
          </h1>
          <p className="profile-sub">
            Your details, travel preferences, saved searches and recent
            searches — all kept private to your account.
          </p>
        </header>

        {notice && (
          <div className="profile-note ok" role="status">
            {notice}
          </div>
        )}
        {error && (
          <div className="profile-note bad" role="alert">
            {error}
          </div>
        )}

        {loading && <p className="profile-empty">Loading your account…</p>}

        {!loading && loadError && (
          <div className="profile-note bad" role="alert">
            {loadError}{" "}
            <Link href="/signin?next=/profile" className="profile-inline-link">
              Sign in again
            </Link>
          </div>
        )}

        {!loading && !loadError && account && (
          <div className="profile-grid">
            <section className="profile-card profile-identity">
              <div className="pf-avatar-wrap">
                {avatarUrl ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img className="pf-avatar" src={avatarUrl} alt="" />
                ) : (
                  <span className="pf-avatar pf-avatar-fallback">
                    {initial}
                  </span>
                )}
                <input
                  ref={avatarInput}
                  type="file"
                  accept="image/*"
                  hidden
                  onChange={onAvatarFile}
                />
                <button
                  type="button"
                  className="pf-btn ghost"
                  onClick={chooseAvatar}
                  disabled={uploading}
                >
                  {uploading ? "Uploading…" : "Change photo"}
                </button>
              </div>
              <div className="pf-id-copy">
                <h2>{identity}</h2>
                <p className="pf-email">{account.email ?? "No email on file"}</p>
                <div className="pf-badges">
                  {account.email_verified ? (
                    <span className="pf-badge verified">Email verified</span>
                  ) : (
                    <span className="pf-badge unverified">Email unverified</span>
                  )}
                  <span className="pf-badge">
                    Member since {when(account.profile?.created_at)}
                  </span>
                </div>
                {!account.email_verified && account.email && (
                  <button
                    type="button"
                    className="pf-btn ghost"
                    onClick={resendVerification}
                    disabled={resending}
                  >
                    {resending ? "Sending…" : "Resend verification email"}
                  </button>
                )}
              </div>
            </section>

            <section className="profile-card">
              <div className="pf-card-head">
                <h2>Profile details</h2>
                <p className="mini">Used to prefill your searches</p>
              </div>
              <form className="pf-form" onSubmit={saveProfile}>
                <label className="pf-field">
                  <span className="cap mini">Full name</span>
                  <input
                    value={form.full_name}
                    onChange={(e) => patchForm({ full_name: e.target.value })}
                    autoComplete="name"
                    required
                  />
                </label>
                <label className="pf-field">
                  <span className="cap mini">
                    Phone <i>optional</i>
                  </span>
                  <input
                    value={form.phone_number}
                    onChange={(e) =>
                      patchForm({ phone_number: e.target.value })
                    }
                    autoComplete="tel"
                    placeholder="+919876543210"
                  />
                </label>
                <label className="pf-field">
                  <span className="cap mini">
                    Home city <i>optional</i>
                  </span>
                  <input
                    value={form.home_city}
                    onChange={(e) => patchForm({ home_city: e.target.value })}
                    placeholder="Delhi"
                  />
                </label>
                <div className="pf-field pf-field-ac">
                  <AirportField
                    value={form.home_airport}
                    onChange={(v) => patchForm({ home_airport: v })}
                  />
                </div>
                <label className="pf-field pf-select">
                  <span className="cap mini">Preferred currency</span>
                  <select
                    value={form.preferred_currency}
                    onChange={(e) =>
                      patchForm({ preferred_currency: e.target.value })
                    }
                  >
                    {CURRENCIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="pf-actions">
                  <button
                    type="submit"
                    className="pf-btn"
                    disabled={savingProfile}
                  >
                    {savingProfile ? "Saving…" : "Save profile"}
                  </button>
                </div>
              </form>
            </section>

            <section className="profile-card">
              <div className="pf-card-head">
                <h2>Travel preferences</h2>
                <p className="mini">Shape future recommendations</p>
              </div>
              <form className="pf-form" onSubmit={savePrefs}>
                <label className="pf-field pf-select">
                  <span className="cap mini">Travel type</span>
                  <select
                    value={prefs.preferred_travel_type}
                    onChange={(e) =>
                      patchPrefs({ preferred_travel_type: e.target.value })
                    }
                  >
                    <option value="">No preference</option>
                    {TRAVEL_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {prettyType(t)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="pf-field pf-select">
                  <span className="cap mini">Preferred cabin</span>
                  <select
                    value={prefs.preferred_cabin}
                    onChange={(e) =>
                      patchPrefs({ preferred_cabin: e.target.value })
                    }
                  >
                    <option value="">No preference</option>
                    {CABINS.map((c) => (
                      <option key={c} value={c}>
                        {prettyType(c.replaceAll("_", " "))}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="pf-field pf-select">
                  <span className="cap mini">Hotel rating</span>
                  <select
                    value={String(prefs.preferred_hotel_rating)}
                    onChange={(e) =>
                      patchPrefs({
                        preferred_hotel_rating: Number(e.target.value),
                      })
                    }
                  >
                    {RATINGS.map((r) => (
                      <option key={r} value={r}>
                        {r === 0 ? "Any rating" : `${r} star${r === 1 ? "" : "s"}`}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="pf-check">
                  <input
                    type="checkbox"
                    checked={prefs.notification_enabled}
                    onChange={(e) =>
                      patchPrefs({ notification_enabled: e.target.checked })
                    }
                  />
                  <span>Email me fare and stay alerts</span>
                </label>
                <div className="pf-actions">
                  <button
                    type="submit"
                    className="pf-btn"
                    disabled={savingPrefs}
                  >
                    {savingPrefs ? "Saving…" : "Save preferences"}
                  </button>
                </div>
              </form>
            </section>

            <section className="profile-card">
              <div className="pf-card-head">
                <h2>Consents</h2>
                <p className="mini">Accepted policy versions</p>
              </div>
              {account.consents.length === 0 ? (
                <p className="profile-empty">
                  No consent records were returned for this account.
                </p>
              ) : (
                <ul className="pf-consents">
                  {account.consents.map((c, i) => (
                    <li key={`${c.consent_type}-${c.policy_version}-${i}`}>
                      <span>{prettyType(c.consent_type.replaceAll("_", " "))}</span>
                      <b>{c.policy_version}</b>
                      <span className="dim">{when(c.accepted_at)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="profile-card profile-wide">
              <div className="pf-card-head">
                <h2>Saved searches</h2>
                <p className="mini">
                  {saves.length} saved · rename or remove any time
                </p>
              </div>
              {listsError && (
                <p className="profile-empty bad">{listsError}</p>
              )}
              {!listsError && saves.length === 0 && (
                <p className="profile-empty">
                  Nothing saved yet. Run a flight, stay or package search and
                  use “Save this search”.
                </p>
              )}
              {saves.length > 0 && (
                <ul className="pf-list">
                  {saves.map((s) => (
                    <li key={s.id} className="pf-row">
                      <div className="pf-row-main">
                        <div className="pf-row-title">
                          <span className="pf-type">{prettyType(s.search_type)}</span>
                          {renameId === s.id ? (
                            <input
                              className="pf-rename"
                              value={renameValue}
                              onChange={(e) => setRenameValue(e.target.value)}
                              maxLength={80}
                              autoFocus
                            />
                          ) : (
                            <b>{s.search_name}</b>
                          )}
                        </div>
                        <p className="pf-row-sub">{summarize(s.search_params)}</p>
                        <p className="pf-row-meta mini">
                          saved {when(s.created_at)}
                        </p>
                      </div>
                      <div className="pf-row-actions">
                        {renameId === s.id ? (
                          <>
                            <button
                              type="button"
                              className="pf-btn small"
                              onClick={() => commitRename(s.id)}
                              disabled={rowBusy === s.id}
                            >
                              {rowBusy === s.id ? "Saving…" : "Save name"}
                            </button>
                            <button
                              type="button"
                              className="pf-btn ghost small"
                              onClick={() => setRenameId(null)}
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              type="button"
                              className="pf-btn ghost small"
                              onClick={() => beginRename(s)}
                            >
                              Rename
                            </button>
                            <button
                              type="button"
                              className="pf-btn danger small"
                              onClick={() => removeSave(s)}
                              disabled={rowBusy === s.id}
                            >
                              Delete
                            </button>
                          </>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="profile-card profile-wide">
              <div className="pf-card-head">
                <h2>Search history</h2>
                <div className="pf-head-actions">
                  <p className="mini">{history.length} recent</p>
                  {history.length > 0 && (
                    <button
                      type="button"
                      className="pf-btn ghost small"
                      onClick={clearAllHistory}
                      disabled={rowBusy === "history-all"}
                    >
                      {rowBusy === "history-all" ? "Clearing…" : "Clear all"}
                    </button>
                  )}
                </div>
              </div>
              {!listsError && history.length === 0 && (
                <p className="profile-empty">
                  No searches recorded yet. Your live searches appear here.
                </p>
              )}
              {history.length > 0 && (
                <ul className="pf-list">
                  {history.map((h) => (
                    <li key={h.id} className="pf-row">
                      <div className="pf-row-main">
                        <div className="pf-row-title">
                          <span className="pf-type">
                            {prettyType(h.search_type)}
                          </span>
                          <b>{summarize(h.search_params)}</b>
                        </div>
                        <p className="pf-row-meta mini">
                          searched {when(h.searched_at)}
                        </p>
                      </div>
                      <div className="pf-row-actions">
                        <button
                          type="button"
                          className="pf-btn danger small"
                          onClick={() => removeHistory(h)}
                          disabled={rowBusy === h.id}
                        >
                          {rowBusy === h.id ? "Removing…" : "Delete"}
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
