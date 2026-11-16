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
  let { data } = await supabase.auth.getSession();
  let token = data.session?.access_token;
  if (!token && allowRefresh) {
    const refreshed = await supabase.auth.refreshSession();
    token = refreshed.data.session?.access_token;
  }
  if (!token) throw new Error("You're signed out — sign in and try again.");

  const res = await fetch(`/api/account${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
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

export const ensureAvatarBucket = () =>
  authedFetch<{ bucket: string; created: boolean }>("/avatar/bucket", {
    method: "POST",
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

export async function uploadAvatar(file: File): Promise<string> {
  await ensureAvatarBucket();
  const supabase = getSupabaseBrowserClient();
  const { data } = await supabase.auth.getSession();
  const user = data.session?.user;
  if (!user) throw new Error("You're signed out — sign in and try again.");
  if (file.size > 2 * 1024 * 1024) throw new Error("Avatar must be under 2 MB.");
  if (!file.type.startsWith("image/")) throw new Error("Choose an image file.");

  const ext = (file.name.split(".").pop() || "png").toLowerCase();
  const path = `${user.id}/${Date.now()}.${ext}`;
  const { error } = await supabase.storage
    .from("avatars")
    .upload(path, file, { upsert: false, contentType: file.type });
  if (error) throw new Error(error.message);

  const { data: publicUrl } = supabase.storage.from("avatars").getPublicUrl(path);
  return publicUrl.publicUrl;
}
