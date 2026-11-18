# Voyage

Voyage is a travel planning web app for searching **flights**, **stays**, and
**curated trip packages** — with built-in ML models that predict fares and
nightly rates before you book.

- **Flights** — live round-trip fares via Google Flights (SerpApi), segmented into outbound / inbound / recommended pairs
- **Stays** — live hotel boards via Google Hotels (SerpApi), with ratings, amenities and estimates
- **Packages** — one flight board + one hotel board combined into three priced tiers (Essential / Curated / Grand) against your budget
- **Insights** — ML price prediction: an indicative flight fare from route, timing, cabin and booking window, and a hotel average-daily-rate (ADR) prediction

Every live SerpApi search is cached on disk — identical repeat searches are
served instantly and cost zero API credits. Airport autocomplete is served
from a bundled local IATA dataset and never touches the network.

## Architecture

| Layer    | Tech                                                              |
| -------- | ----------------------------------------------------------------- |
| Frontend | Next.js (App Router) · React · TypeScript · plain CSS             |
| Backend  | Python · Flask (blueprints) · PyTorch + scikit-learn models        |
| Data     | SerpApi (Google Flights / Google Hotels) · Aviationstack key (`AVAITION_API`, reserved for future use) · local IATA JSON dataset |
| Proxy    | Next.js rewrites `/api/*` → Flask on `127.0.0.1:6050`              |

```
Voyage/
├── backend/
│   ├── __main__.py          # Flask app entrypoint (port 6050)
│   ├── src/
│   │   ├── routes/          # flights, hotels, packages blueprints
│   │   └── services/        # serp_service (cache-first), flight/package services
│   ├── model/               # trained .pth / scaler.pkl artifacts + builders
│   ├── data/                # IATA dataset, serp_cache/
│   └── notebooks/           # model development notebooks
├── frontend/
│   ├── app/                 # page.tsx (single-page console), chrome.tsx
│   ├── lib/api.ts           # typed client for the Flask API
│   └── next.config.ts       # /api/* proxy to :6050
├── docs/                    # SerpApi endpoint notes
├── requirements.txt
└── .env                     # SERP_API and AVAITION_API keys (not committed)
```

## Getting Started

### 1. Backend (Python)

```bash
# from the project root, using a virtualenv
python -m venv venv
venv\Scripts\activate            # Windows (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
python -m backend                # starts Flask on http://127.0.0.1:6050
```

Create a `.env` at the project root with your API keys:

```
SERP_API=<your-serpapi-key>       # required — powers Google Flights / Google Hotels search
AVAITION_API=<your-aviationstack-key>  # reserved for future use, not yet read by the code
```

### 2. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev                      # http://localhost:3000
```

The frontend proxies all `/api/*` requests to the Flask backend, so both
processes must be running. To use the ML prediction endpoints, run the model
artifact builder first if the `.pth`/`.pkl` files are missing
(`backend/model/build_flight_artifacts.py` and `rebuild.py`).

## Authentication & account data (Supabase)

Sign-in, email verification, password reset, profile editing, saved searches and
search history use Supabase Auth plus the existing tables `profiles`,
`user_preferences`, `user_consents`, `saved_searches` and `search_history`.
Keep RLS enabled; the Flask account API always calls PostgREST with the caller's
own access token.

Add these values to the root `.env`:

```
NEXT_PUBLIC_SUPABASE_URL=https://your-project-ref.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=your-publishable-anon-key
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SECRET_KEY=your-secret-service-key   # server-only, never expose it
# SUPABASE_JWT_SECRET=...                     # only for legacy HS256 projects
# FRONTEND_ORIGIN=http://localhost:3000       # optional CORS origin(s), comma-separated
```

Supabase Auth URL configuration (required for real email links):

- In the Supabase dashboard open **Authentication → URL Configuration**.
- Set **Site URL** to the app origin (`http://localhost:3000` in development, the
  production origin in production).
- Add every callback URL to **Redirect URLs**:
  - `http://localhost:3000/auth/callback`
  - `https://<your-production-origin>/auth/callback`
- Sign-up, password-reset and resend links all point at `/auth/callback`, which
  verifies the token and then redirects to the local `next` path. If these URLs
  are missing, Supabase rewrites the link to the Site URL and the verification
  session never reaches the callback.
- After configuring them, send yourself a real sign-up and reset email and open
  the link in the same browser (the PKCE verifier is stored there). The
  integration script below cannot click a real inbox link.

Database prerequisites:

- The `handle_new_user()` trigger creates the profile, preferences and consent rows.
  Consent rows are trigger-only by default: `authenticated` has no `INSERT` grant
  on `public.user_consents`, so direct client inserts are denied even though an
  owner-insert policy exists. Grant `INSERT` only if direct client consent writes
  are required.
- The `authenticated` role must be allowed to update only the profile columns users
  may edit. If profile saves return `permission denied for table profiles`, run:

```sql
GRANT UPDATE (
  full_name, phone_number, home_city, home_airport, preferred_currency, avatar_url
) ON public.profiles TO authenticated;
```

  `updated_at` stays server-managed by the table trigger and is intentionally not
  granted.

- The public `avatars` bucket is created on demand by the authenticated
  `POST /api/account/avatar/bucket` endpoint; the secret key never leaves the server.
  Storage RLS must allow each user to write only inside their own `<user_id>/` folder:

```sql
drop policy if exists "avatars: owner select" on storage.objects;
drop policy if exists "avatars: owner insert" on storage.objects;
drop policy if exists "avatars: owner update" on storage.objects;
drop policy if exists "avatars: owner delete" on storage.objects;

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
```

  The bucket is public, so direct public-URL downloads work without a select
  policy, but the Storage API still needs an owner `SELECT` policy for listing,
  signed URLs, overwrite/upsert and delete. Without it, owner delete/upsert
  returns `Access denied` even though the insert/update/delete policies exist.
  The select policy above only exposes each user's own folder.

Run the backend and frontend, then exercise the full auth flow from the repo root:

```bash
python -m backend
cd frontend
npm run dev
# in another terminal, from the repo root:
python backend/tests_dev/test_auth_integration.py --frontend http://localhost:3000
```

The integration script creates and deletes real test users. It covers the trigger,
JWT verification, profile/preferences, saved searches, history, RLS isolation,
CORS, protected-route redirects and real signup/recovery callbacks using
admin-generated token hashes. It cannot click a link in a real inbox.

## Security & production

- **Rotate provider keys.** `SERP_API` and `AVAITION_API` were committed in an
  old `env` file (now purged from history and ignored). Treat them as compromised:
  issue new keys in the SerpApi / Aviationstack dashboards and update `.env`.
  Never commit `.env` or any file named `env`.
- **Database rules.** Run `docs/supabase-security.sql` in the Supabase SQL editor
  to enforce owner-only RLS on the account tables plus the avatar storage folder.
- **Production runtime.** Set `APP_ENV=production`, `FLASK_DEBUG=0`, a
  comma-separated `FRONTEND_ORIGIN` of `https://` origins, and `TRUST_PROXY=1`
  only behind a trusted reverse proxy. Install `requirements.txt` and serve Flask
  with waitress instead of the dev server:

  ```bash
  python -m backend.serve
  ```

  Terminate TLS at the proxy and keep `NEXT_PUBLIC_SUPABASE_URL` on `https`.
- **Abuse controls.** All `/api/*` routes are rate-limited per IP and every
  cache-miss SerpApi search consumes `SERP_DAILY_CALL_LIMIT` (default 200/day).
  Tune the limits in `.env.example`; `0` disables a limit.
- **Browser hardening.** Next.js sets CSP, HSTS (production), nosniff,
  frame-denial and referrer/permissions policies; Supabase auth cookies are
  `SameSite=Lax` and `Secure` in production. The CSP keeps `'unsafe-inline'`
  for Next's bootstrap scripts; move to nonce-based CSP when the app no longer
  needs inline scripts.

## API Reference

All endpoints are served through the Next.js proxy at `/api` (Flask on `:6050`).

### Flights — `/api/flight`
| Method | Endpoint    | Description                                                              |
| ------ | ----------- | ------------------------------------------------------------------------ |
| GET    | `/options`  | Dropdown values + duration / days-left ranges for the prediction form    |
| POST   | `/predict`  | Predicted fare for a flight query (single object or batch list)          |
| GET    | `/airports` | Local IATA autocomplete (`?q=del&limit=8`) — no API credit spent         |
| GET    | `/search`   | Live Google Flights round trip (`origin`, `destination`, `outbound_date`, `return_date`, optional `travel_class`, `adults`, `children`) |

### Stays — `/api/hotel`
| Method | Endpoint   | Description                                                                        |
| ------ | ---------- | ------------------------------------------------------------------------------------ |
| GET    | `/options` | Top category values from training data for the prediction form                       |
| POST   | `/predict` | Predicted ADR from hotel type, arrival date, stay length and party size             |
| GET    | `/search`  | Live Google Hotels board (`q`, `check_in_date`, `check_out_date`, optional `sort_by`, `adults`, `children`) |

### Packages — `/api/package`
| Method | Endpoint  | Description                                                                                                          |
| ------ | --------- | ---------------------------------------------------------------------------------------------------------------------- |
| GET    | `/search` | Three package tiers from one flight + one hotel board (`origin`, `destination`, `q`, `outbound_date`, `return_date`, `budget`, optional `cabin`, `adults`, `children`) |

Responses on the live boards include `cached` and `fetched_on` so the UI can
label results as *Live* or *Cached*.

## Models

The prediction endpoints are backed by artifacts in `backend/model/`:

- **Flights** (`Flights.py`, `flight_price_model_01.pth`, `flight_scaler.pkl`) — PyTorch regression on route, airline, cabin, departure/arrival windows, stops, duration and days-until-booking
- **Hotels** (`Hotels.py`, `hotel_price.pth`, `hotel_scaler.pkl`) — predicts average daily rate from hotel type, arrival month/week/day, weekend vs. week nights and party size
- `flight_meta.json` / `hotel_meta.json` expose the allowed option values to the frontend via the `/options` endpoints

Notebooks and training scripts live in `backend/notebooks/`.
