# /api/hotel/predict must return INR-scale values (the ADR model is EUR-based;
# the app displays everything in rupees).
# Run:  python backend/test_hotel_predict_inr.py   (from the project root)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.__main__ import app

BODY = {
    "hotel": "City Hotel",
    "arrival_date_year": 2016,
    "arrival_date_month": "August",
    "arrival_date_week_number": 33,
    "arrival_date_day_of_month": 16,
    "stays_in_weekend_nights": 1,
    "stays_in_week_nights": 2,
    "adults": 2,
}

EUR_ADR_EXPECTED = 117.76   # served model's raw EUR estimate for this row
RATE_MIN, RATE_MAX = 100.0, 110.0   # plausible EUR->INR band

client = app.test_client()
res = client.post("/api/hotel/predict", json=BODY)
assert res.status_code == 200, res.get_json()
data = res.get_json()

adr = data["adr"][0]
implied_rate = adr / EUR_ADR_EXPECTED
assert RATE_MIN <= implied_rate <= RATE_MAX, (
    f"adr {adr} is not INR-scale (implied FX {implied_rate:.2f})"
)
assert data.get("currency") == "INR", data

print("OK adr=", round(adr, 2), "implied_fx=", round(implied_rate, 2))
