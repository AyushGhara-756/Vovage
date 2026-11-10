# Vovage

Vovage is a travel planning web app for searching **flights**, **stays**, and
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
Vovage/
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
