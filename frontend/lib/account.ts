import { validateAvatarFile } from "@/lib/avatar";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

export type Profile = {
  id: string;
  full_name: string | null;
  phone_number: string | null;
  home_city: string | null;
  home_airport: string | null;
  preferred_currency: string | null;
  avatar_url: string | null;
  created_at: string;
  updated_at: string;
};

export type Preferences = {
  preferred_travel_type: string | null;
  preferred_cabin: string | null;
  preferred_hotel_rating: number | null;
  notification_enabled: boolean | null;
};

export type Consent = {
  consent_type: string;
  policy_version: string;
  accepted_at: string;
};

export type AccountPayload = {
  user_id: string;
  email: string | null;
  email_verified: boolean;
  profile: Profile | null;
  preferences: Preferences | null;
  consents: Consent[];
};

export type SavedSearch = {
  id: string;
  search_type: string;
  search_name: string;
  search_params: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type HistoryEntry = {
  id: string;
  search_type: string;
  search_params: Record<string, unknown>;
  searched_at: string;
};

async function authedFetch<T>(
  path: string,
  init: RequestInit = {},
  allowRefresh = true,
): Promise<T> {
  const supabase = getSupabaseBrowserClient();
  const { data } = await supabase.auth.getSession();
  let token = data.session?.access_token;
  if (!token && allowRefresh) {
    const refreshed = await supabase.auth.refreshSession();
    token = refreshed.data.session?.access_token;
  }
  if (!token) throw new Error("You're signed out — sign in and try again.");

  const isFormData =
    typeof FormData !== "undefined" && init.body instanceof FormData;
  const res = await fetch(`/api/account${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      Authorization: `Bearer ${token}`,
      ...(init.headers ?? {}),
    },
  });

  if (res.status === 401 && allowRefresh) {
    const { data: refreshed } = await supabase.auth.refreshSession();
    if (refreshed.session) return authedFetch<T>(path, init, false);
  }

  const body = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) {
    throw new Error(
      (body.error as string) ?? `request failed (${res.status})`,
    );
  }
  return body as T;
}

export const fetchAccount = () => authedFetch<AccountPayload>("/me");

export const updateAccount = (updates: Partial<{
  full_name: string;
  phone_number: string;
  home_city: string;
  home_airport: string;
  preferred_currency: string;
  avatar_url: string;
  preferred_travel_type: string;
  preferred_cabin: string;
  preferred_hotel_rating: number;
  notification_enabled: boolean;
}>) =>
  authedFetch<AccountPayload>("/me", {
    method: "PATCH",
    body: JSON.stringify(updates),
  });

export const listSaves = () => authedFetch<{ saves: SavedSearch[] }>("/saves");

export const createSave = (p: {
  search_type: string;
  search_name: string;
  search_params: Record<string, unknown>;
}) =>
  authedFetch<{ save: SavedSearch }>("/saves", {
    method: "POST",
    body: JSON.stringify(p),
  });

export const updateSave = (
  id: string,
  updates: { search_name?: string; search_params?: Record<string, unknown> },
) =>
  authedFetch<{ save: SavedSearch }>(`/saves/${id}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });

export const deleteSave = (id: string) =>
  authedFetch<{ deleted: string }>(`/saves/${id}`, { method: "DELETE" });

export const listHistory = () =>
  authedFetch<{ history: HistoryEntry[] }>("/history");

export const recordHistory = (p: {
  search_type: string;
  search_params: Record<string, unknown>;
}) =>
  authedFetch<{ history: HistoryEntry }>("/history", {
    method: "POST",
    body: JSON.stringify(p),
  });

export async function recordHistoryIfSignedIn(p: {
  search_type: string;
  search_params: Record<string, unknown>;
}): Promise<void> {
  const { data } = await getSupabaseBrowserClient().auth.getSession();
  if (!data.session) return;
  try {
    await recordHistory(p);
  } catch {
    /* history is best-effort; never block a live search */
  }
}

export const deleteHistory = (id: string) =>
  authedFetch<{ deleted: string }>(`/history/${id}`, { method: "DELETE" });

export const clearHistory = () =>
  authedFetch<{ cleared: boolean }>("/history", { method: "DELETE" });

export function uploadAvatar(file: File): Promise<AccountPayload> {
  validateAvatarFile(file);
  const body = new FormData();
  body.append("file", file);
  return authedFetch<AccountPayload>("/avatar", { method: "POST", body });
}
