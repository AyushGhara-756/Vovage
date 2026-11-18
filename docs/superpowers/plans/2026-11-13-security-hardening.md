# Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the committed live-key leak and close the missing controls from the 20-point security audit.

**Architecture:** Keep the current Next.js + Flask split. Add a small, dependency-free Flask security module for per-IP rate limits and a persistent daily SerpApi call cap, add response security headers in Next and Flask, make cookie/debug/production settings explicit, and tighten uploads and external links.

**Tech Stack:** Next.js 16 (App Router), React 19, TypeScript, Flask 3, Supabase (`@supabase/ssr`), Python stdlib.

**Spec:** This plan implements the audit in the 2026-11-13 conversation. No separate design file.

## Global Constraints

- Do not print or log secret values.
- `.env` stays server-only; only `NEXT_PUBLIC_*` values may reach the browser.
- All new behaviour is configurable through environment variables with safe defaults.
- Keep the existing public API shapes unchanged.
- No new Python dependency unless required for production serving.

## Review Focus

- A request flood must receive `429` without reaching SerpApi.
- The daily cap must survive process restarts and reset at local midnight.
- Security headers must not break Next dev (`unsafe-eval`) or remote images.
- Cookies must stay usable over local HTTP while being `Secure` in production.
- Invalid or `javascript:` result URLs must never become clickable links.

---

### Task 1: Remove the committed `env` leak

**Files:**
- Modify: `.gitignore`
- History: all local branches and tags

**Interfaces:**
- Produces: no `env` blob in history; `env` ignored going forward.

- [ ] **Step 1: Add `env` to `.gitignore`** next to `.env`.
- [ ] **Step 2: Back up refs** to `C:\Users\HOME\AppData\Local\Temp\opencode\Voyage-pre-filter.bundle`.
- [ ] **Step 3: Rewrite history** with `git filter-branch --index-filter "git rm --cached --ignore-unmatch env" --prune-empty -- --all`.
- [ ] **Step 4: Expire reflogs and gc**; delete `refs/original`.
- [ ] **Step 5: Verify** no current secret value appears in any commit; force-push `main` and `swayam`.

### Task 2: Rate limiting + SerpApi daily spend cap

**Files:**
- Create: `backend/src/security.py`
- Modify: `backend/__main__.py`, `backend/src/services/serp_service.py`
- Test: `backend/tests_dev/test_security.py`

**Interfaces:**
- Produces: `RateLimiter`, `rate_limit(bucket, per_minute)`, `QuotaError`, `reserve_serp_call()`.
- `reserve_serp_call()` raises `QuotaError` once `SERP_DAILY_CALL_LIMIT` is exhausted.

- [ ] **Step 1: Write failing tests** for allow-then-429, per-IP isolation, quota persistence, and quota reset on a new day.
- [ ] **Step 2: Run tests and confirm failure.**
- [ ] **Step 3: Implement** the limiter, quota store, and Flask hooks (`429` with `Retry-After`; `QuotaError` -> `429`).
- [ ] **Step 4: Run tests and confirm pass.**
- [ ] **Step 5: Commit.**

### Task 3: Flask production settings

**Files:**
- Modify: `backend/__main__.py`
- Create: `backend/serve.py`
- Modify: `requirements.txt`

**Interfaces:**
- `HOST`, `PORT`, `FLASK_DEBUG` control `app.run`; `serve.py` uses waitress.

- [ ] **Step 1: Make debug explicit** (`FLASK_DEBUG=1` only) and read `HOST`/`PORT`.
- [ ] **Step 2: Validate `FRONTEND_ORIGIN` in production** and reject `*`.
- [ ] **Step 3: Add API security headers** via `after_request`.
- [ ] **Step 4: Add `backend/serve.py`** using waitress and document it.
- [ ] **Step 5: Verify import and tests.**

### Task 4: Next.js security headers + env validation

**Files:**
- Modify: `frontend/next.config.ts`

- [ ] **Step 1: Validate required `NEXT_PUBLIC_*` vars** at config load with a clear error.
- [ ] **Step 2: Add `headers()`** for CSP, nosniff, frame denial, referrer, permissions, COOP/CORP, and production-only HSTS.
- [ ] **Step 3: Run `npm run build`.**

### Task 5: Explicit Supabase cookie options

**Files:**
- Create: `frontend/lib/supabase/cookie-options.ts`
- Modify: `frontend/lib/supabase/client.ts`, `server.ts`, `frontend/proxy.ts`, `frontend/app/auth/callback/route.ts`

- [ ] **Step 1: Add `{ path: "/", sameSite: "lax", secure: production }`.**
- [ ] **Step 2: Pass `cookieOptions` to every Supabase client.**
- [ ] **Step 3: Run `npm run build`.**

### Task 6: Upload hardening

**Files:**
- Modify: `frontend/lib/account.ts`, `frontend/app/profile/page.tsx`, `backend/src/routes/account.py`

- [ ] **Step 1: Whitelist MIME types client-side** and derive the extension from MIME, not the filename.
- [ ] **Step 2: Narrow the file input `accept`.**
- [ ] **Step 3: Update an existing avatar bucket's limit/MIME config**, not only create it.
- [ ] **Step 4: Run `npm run build`.**

### Task 7: External link scheme validation

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Add `safeHref(value)`** returning the URL only for `http:`/`https:`.
- [ ] **Step 2: Use it in `StayCard` and `PackageCard`.**
- [ ] **Step 3: Run `npm run build`.**

### Task 8: Database rules + env documentation

**Files:**
- Create: `docs/supabase-security.sql`
- Modify: `.env.example`, `README.md`

- [ ] **Step 1: Ship owner-only RLS policies** for the five user tables and the avatar storage policies.
- [ ] **Step 2: Document the new rate/quota/production variables.**
- [ ] **Step 3: Tell the operator to rotate `SERP_API` and `AVAITION_API`.**

### Task 9: Final verification

- [ ] **Step 1: Run backend security tests** and existing fail-closed tests.
- [ ] **Step 2: Run `npm run build`.**
- [ ] **Step 3: Re-scan history for leaked values.**
- [ ] **Step 4: `git status` and summarize remaining operator actions.**
