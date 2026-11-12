# Vovage Supabase Auth + Backend Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Finish and harden the existing Vovage Supabase auth, profile, saved-search/history, and Flask integration so the full flow works end to end under RLS.

**Architecture:** Next.js 16 App Router with `@supabase/ssr` browser/server clients and Next 16 `proxy.ts` session refresh + route protection. Flask verifies Supabase asymmetric JWTs via JWKS and performs all user data access with the caller's own access token through PostgREST, leaving RLS in force.

**Tech Stack:** Next.js 16.4.5, React 19, TypeScript, `@supabase/ssr`, `@supabase/supabase-js`, Flask, `supabase` Python, PyJWT, httpx.

**Spec:** User-provided task brief (2026-11-12) plus confirmed `handle_new_user()` consent validation.

## Global Constraints

- Never expose or log `SUPABASE_SECRET_KEY`; browser uses only `NEXT_PUBLIC_*`.
- Never store passwords in custom tables; Supabase Auth owns passwords.
- Never trust a user id from a request body; only the verified JWT `sub`.
- Keep RLS enabled; use the user JWT for normal data access.
- Do not create tables or duplicate profile insertion; the trigger owns creation.
- Preserve the existing Vovage visual design and unrelated functionality.
- Do not mark email verified manually or disable confirmation.
- `.env` stays untracked; `.env.example` contains placeholders only.

## Review Focus

- Expired/invalid verification or reset links must show a recovery path, not a blank or raw error.
- Duplicate signup must not look like success (Supabase returns an obfuscated user with no identities).
- A signed-out visitor must never reach `/profile` or `/api/account/*`.
- One user must not read, rename, or delete another user's saved searches/history/profile.
- Backend must fail closed (401) when JWKS/env is misconfigured, and never fall back to unverified decoding.

---

### Task 1: Repair the current build and env loading

**Files:**
- Modify: `frontend/app/chrome.tsx`
- Modify: `frontend/lib/supabase/server.ts`
- Modify: `frontend/app/forgot-password/page.tsx`
- Modify: `backend/src/flask_auth.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `getSupabaseServerClient(): Promise<SupabaseClient>`; `flask_auth` reads root `.env` correctly.

- [x] Fix implicit-any auth callbacks in `chrome.tsx` with `Session | null` types.
- [x] Make `getSupabaseServerClient` `async` (it awaits `cookies()`).
- [x] Fix `forgot-password` missing `useRouter` import (remove unused router).
- [x] Change Flask `ROOT` from `parents[3]` to `parents[2]` so `D:\Projects\Vovage\.env` is found.
- [x] Add `.env*` + `!.env.example` to root `.gitignore`.
- [x] Run `npm run build` and `python -m compileall backend`; expect pass.

### Task 2: Auth pages, verification, reset, and session UX

**Files:**
- Modify: `frontend/app/signin/page.tsx`
- Modify: `frontend/app/signup/page.tsx`
- Modify: `frontend/app/forgot-password/page.tsx`
- Modify: `frontend/app/auth/update-password/page.tsx`
- Modify: `frontend/app/auth-shared.tsx`
- Modify: `frontend/app/auth/callback/route.ts`
- Modify: `frontend/proxy.ts`

**Interfaces:**
- Callback accepts `code` OR `token_hash` + `type` (`signup`, `email`, `recovery`, `email_change`) and always validates `next` is a local path.
- Sign-in surfaces `verify_error`, `verified=1`, and unverified-email resend.
- Sign-up detects duplicate obfuscated users (`identities.length === 0`).
- Update-password detects missing/expired recovery session.

- [x] Add safe local `next` validation to callback and `verifyOtp` support.
- [x] Add sign-in status banners for verification success/failure and remove the non-functional "remember" control.
- [x] Add duplicate-account detection and optional-field normalization on signup.
- [x] Add session/expired handling to update-password.
- [x] Extend `authErrorMessage` mappings for expired/otp/session errors.
- [x] Keep `/profile` and `/auth/update-password` in proxy matcher; redirect signed-in users away from signin/signup.
- [x] Build must pass.

### Task 3: Profile page and account UI

**Files:**
- Create: `frontend/app/profile/page.tsx`
- Create: `frontend/app/profile/profile.css`
- Modify: `frontend/app/auth-shared.tsx` (export AirportField already exists)

**Interfaces:**
- Uses `fetchAccount`, `updateAccount`, `uploadAvatar`, saved-search/history functions from `lib/account.ts`.
- Renders: identity + verification status, editable profile, preferences, avatar, consent records, saved searches (rename/delete), history (delete/clear).

- [x] Build the page with loading, error, success, and disabled/busy states.
- [x] Reuse existing tokens/classes and add focused profile CSS.
- [x] Ensure every button performs a real action.
- [x] Build must pass.

### Task 4: Saved-search and history integration in the console

**Files:**
- Create: `frontend/app/save-search.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/lib/account.ts`
- Modify: `frontend/app/globals.css` or new `save-search.css`

**Interfaces:**
- `SaveSearchButton({ searchType, params, defaultName })` saves via backend and shows inline feedback.
- `recordHistoryIfSignedIn({ search_type, search_params })` no-ops when signed out and never blocks a search.

- [x] Add save control to flight, stay, and package board heads.
- [x] Record history after each successful live search for signed-in users.
- [x] Show "Sign in to save" link for signed-out users instead of a dead button.
- [x] Build must pass.

### Task 5: Harden Flask account API

**Files:**
- Modify: `backend/src/routes/account.py`
- Modify: `backend/__main__.py`
- Modify: `frontend/lib/account.ts` (only if response shape changes)

**Interfaces:**
- All `/api/account/*` routes require `Authorization: Bearer <user access token>`.
- `PATCH /me` updates only verified user's rows; ignores supplied ids; validates enums/lengths.
- Saves/history CRUD always filters by `g.user_id`.

- [x] Replace literal `"now()"` update values with UTC ISO timestamps.
- [x] Make `me()` tolerate a missing preferences row and return safe errors.
- [x] Keep avatar bucket creation isolated behind auth + secret key; never expose the key.
- [x] Confirm CORS is restricted to `http://localhost:3000`.
- [x] `python -m compileall backend` must pass.

### Task 6: End-to-end verification

**Files:**
- Create: `backend/tests_dev/test_auth_integration.py`
- Modify: `README.md` (auth setup/commands)

**Interfaces:**
- Script creates two confirmed test users through the Auth admin API, verifies trigger rows, signs in, exercises Flask via test client, checks RLS isolation, exercises verification/reset callbacks against `next dev`, then deletes test users.

- [x] Run `npm run build`.
- [x] Run `python -m compileall backend`.
- [x] Run the integration script and record real results.
- [x] Verify callback/redirect protection with the dev server.
- [x] Clean up test users and report limitations (real inbox click cannot be automated).

## Self-Review

- Spec coverage: signup/login/logout, verification, reset, sessions, profile, Flask auth, saved searches, history, security, tests all have tasks.
- Type consistency: callback, account client, and Flask routes use the same field names as the spec/tables.
- Review Focus tests are owned by Task 6.
- Proportion: tasks stay at file/interface level; no full implementation bodies.

## Execution Record (2026-11-12)

- `npm run build` passed (Next.js 16.4.5, TypeScript clean).
- `python -m compileall -q backend` passed.
- `python backend/tests_dev/test_auth_integration.py --frontend http://localhost:3000`:
  **75 passed, 0 failed**. Covers trigger rows, JWKS JWT rejection, profile/preferences,
  saves/history CRUD, RLS isolation, spoofed ids/user_ids, CORS, protected routes,
  and real signup/recovery callbacks using admin-generated token hashes.
- Ruling: do not send `updated_at` in profile/preferences/saved-search updates. The
  database triggers maintain it, and the authenticated role's grant intentionally
  excludes direct writes to `profiles.updated_at`. Verified all three tables advance
  `updated_at` automatically.
- Ruling: `email_verified` is read from GoTrue `/auth/v1/user` (`email_confirmed_at`)
  because the access token has no authoritative top-level verification claim; the
  `user_metadata.email_verified` value is user-editable and is not trusted.
- Database setup applied outside the repo: `GRANT UPDATE` on the editable
  `profiles` columns for `authenticated`; the public `avatars` bucket is created
  idempotently by `POST /api/account/avatar/bucket`.
- Limitation: a real inbox click cannot be automated. Verification and recovery
  links were exercised with admin-generated `hashed_token` values; the script
  creates and deletes real test users.

## Resume Verification Record (2026-11-12, after whole-branch review)

- `npm run build` passed (Next.js 16.4.5, TypeScript clean) after the review fixes.
- `python -m compileall -q backend` passed.
- `node --test frontend/lib/auth-errors.test.mjs frontend/lib/auth-redirect.test.mjs frontend/lib/safe-next.test.mjs`:
  **9 passed**.
- `python -m unittest backend.tests_dev.test_auth_fail_closed -v`: **3 passed**
  (partial Supabase env and JWKS misconfiguration fail closed with 401).
- `python backend/tests_dev/test_auth_integration.py --frontend http://localhost:3000`:
  **75 passed, 0 failed, 1 skipped**. The skip is the avatar upload check: the
  live Supabase project does not currently have the storage RLS policies applied;
  the script now says so explicitly and points at the README SQL. Apply the
  storage policy SQL in README "Authentication & account data" and rerun to
  exercise the avatar checks. The callback checks that previously timed out on a
  cold dev-server compile now pass (fetch timeout raised to 60 s).
- Review fixes applied: re-sent verification emails now pass `emailRedirectTo`
  through `/auth/callback`; cross-device PKCE failures get an actionable message;
  Supabase Auth URL configuration is documented; the account API returns 401
  rather than 500 when `SUPABASE_URL`/publishable key are missing.
- Ruling: missing storage RLS policies are database setup, not a code defect; the
  code already uploads to `<user_id>/...` and the README documents the exact SQL.
- Ruling: the integration script treats an RLS-denied avatar upload as an explicit
  setup skip (with instructions) instead of a code failure, so the security checks
  that do not depend on storage policies stay meaningful.

