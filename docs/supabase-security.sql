-- Run this in the Supabase SQL editor. Service-role requests bypass RLS;
-- every browser/PostgREST request under the user's JWT is constrained here.

alter table public.profiles enable row level security;
alter table public.user_preferences enable row level security;
alter table public.user_consents enable row level security;
alter table public.saved_searches enable row level security;
alter table public.search_history enable row level security;

grant update (
  full_name, phone_number, home_city, home_airport, preferred_currency, avatar_url
) on public.profiles to authenticated;

drop policy if exists "profiles: owner select" on public.profiles;
create policy "profiles: owner select"
on public.profiles for select to authenticated
using (id = auth.uid());

drop policy if exists "profiles: owner update" on public.profiles;
create policy "profiles: owner update"
on public.profiles for update to authenticated
using (id = auth.uid())
with check (id = auth.uid());

drop policy if exists "preferences: owner select" on public.user_preferences;
create policy "preferences: owner select"
on public.user_preferences for select to authenticated
using (user_id = auth.uid());

drop policy if exists "preferences: owner update" on public.user_preferences;
create policy "preferences: owner update"
on public.user_preferences for update to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "consents: owner select" on public.user_consents;
create policy "consents: owner select"
on public.user_consents for select to authenticated
using (user_id = auth.uid());

-- Consent rows are created only by the handle_new_user() trigger (security
-- definer). Browser clients may read their own rows but must never insert,
-- update, or delete them. Removing the old owner-insert policy and revoking
-- writes keeps the audit trail trigger-only and immutable.
drop policy if exists "consents: owner insert" on public.user_consents;
revoke insert, update, delete on public.user_consents from anon, authenticated;

drop policy if exists "saves: owner select" on public.saved_searches;
create policy "saves: owner select"
on public.saved_searches for select to authenticated
using (user_id = auth.uid());

drop policy if exists "saves: owner insert" on public.saved_searches;
create policy "saves: owner insert"
on public.saved_searches for insert to authenticated
with check (user_id = auth.uid());

drop policy if exists "saves: owner update" on public.saved_searches;
create policy "saves: owner update"
on public.saved_searches for update to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "saves: owner delete" on public.saved_searches;
create policy "saves: owner delete"
on public.saved_searches for delete to authenticated
using (user_id = auth.uid());

drop policy if exists "history: owner select" on public.search_history;
create policy "history: owner select"
on public.search_history for select to authenticated
using (user_id = auth.uid());

drop policy if exists "history: owner insert" on public.search_history;
create policy "history: owner insert"
on public.search_history for insert to authenticated
with check (user_id = auth.uid());

drop policy if exists "history: owner delete" on public.search_history;
create policy "history: owner delete"
on public.search_history for delete to authenticated
using (user_id = auth.uid());

drop policy if exists "avatars: owner select" on storage.objects;
drop policy if exists "avatars: owner insert" on storage.objects;
drop policy if exists "avatars: owner update" on storage.objects;
drop policy if exists "avatars: owner delete" on storage.objects;

-- SELECT is required for listing, signed URLs, overwrite/upsert and delete.
-- The bucket stays public for direct public-URL downloads, but this policy
-- keeps the authenticated Storage API scoped to the user's own folder.
create policy "avatars: owner select"
on storage.objects for select to authenticated
using (
  bucket_id = 'avatars'
  and (storage.foldername(name))[1] = auth.uid()::text
);

create policy "avatars: owner insert"
on storage.objects for insert to authenticated
with check (
  bucket_id = 'avatars'
  and (storage.foldername(name))[1] = auth.uid()::text
);

create policy "avatars: owner update"
on storage.objects for update to authenticated
using (
  bucket_id = 'avatars'
  and (storage.foldername(name))[1] = auth.uid()::text
)
with check (
  bucket_id = 'avatars'
  and (storage.foldername(name))[1] = auth.uid()::text
);

create policy "avatars: owner delete"
on storage.objects for delete to authenticated
using (
  bucket_id = 'avatars'
  and (storage.foldername(name))[1] = auth.uid()::text
);
