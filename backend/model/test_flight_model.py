# Sanity check for the served flight-price model.
# Run:  python backend/model/test_flight_model.py   (from the project root)
# Fails if predictions for typical Kaggle-dataset-style rows are absurd.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Flights import load_artifacts, predict_price

ROWS = [
    # budget economy, short hop, booked far ahead -> few thousands
    {"airline": "AirAsia", "source_city": "Bangalore",
     "departure_time": "Morning", "stops": "zero",
     "arrival_time": "Afternoon", "destination_city": "Chennai",
     "class": "Economy", "duration": 90, "days_left": 50},
    # full-service business, trunk route -> tens of thousands
    {"airline": "Vistara", "source_city": "Delhi",
     "departure_time": "Morning", "stops": "zero",
     "arrival_time": "Afternoon", "destination_city": "Mumbai",
     "class": "Business", "duration": 135, "days_left": 10},
]

ECONOMY_MAX = 60_000    # BOM-DEL-style economy fares never approach 1e5 in the dataset
BUSINESS_MIN = 15_000   # business class is never cheaper than a budget economy seat
BUSINESS_MAX = 150_000

model, scaler, meta = load_artifacts()
prices = [float(p) for p in predict_price(model, scaler, meta, ROWS)]
economy, business = prices

assert ECONOMY_MAX / 10 <= economy <= ECONOMY_MAX, f"economy fare absurd: {economy}"
assert BUSINESS_MIN <= business <= BUSINESS_MAX, f"business fare absurd: {business}"
assert business > economy, f"business ({business}) must exceed economy ({economy})"

print("OK", [round(p, 1) for p in prices])
