# SerpApi round-trip options carry only outbound legs and are priced as full
# round trips per traveller. Boards whose options lack prices (Google often
# can't quote smaller/regional routes, e.g. BOM->PNQ) must not be priced.
# Run:  python backend/test_roundtrip_shape.py   (from the project root)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.src.services.serp_service import shape_flight
from backend.src.services.package_service import PackageError, build_packages


def _leg(dep, arr):
    return {"departure_airport": {"id": dep, "name": dep, "time": "2026-11-20 10:00"},
            "arrival_airport": {"id": arr, "name": arr, "time": "2026-11-20 12:00"},
            "duration": 120}


def _raw_rt(options):
    return {
        "search_parameters": {"departure_id": "BOM", "arrival_id": "PNQ",
                              "outbound_date": "2026-11-20",
                              "return_date": "2026-11-25", "currency": "INR"},
        "best_flights": options,
    }


# 1) shaping: outbound-only legs survive (that's how SerpApi quotes round trips)
shaped = shape_flight(_raw_rt([{"flights": [_leg("BOM", "DEL")], "price": 27758}]))
assert len(shaped["best"]) == 1, "valid round-trip quote was wrongly dropped"

# 2) packages: a board whose every option is unpriced can't be priced
unpriced_board = {
    "currency": "INR",
    "best": [{"price": None,
              "legs": [{"dep_code": "BOM"}, {"arr_code": "PNQ"}]}],
    "others": [], "selected": [], "trip": {"origin": "BOM", "destination": "PNQ"},
}
hotel = {"currency": "INR", "q": "Pune",
         "properties": [{"name": "S", "total_price": 5000, "rating": 4.0,
                         "images": [], "nearby": [], "amenities": []}]}
try:
    build_packages(unpriced_board, hotel, 50000, nights=5, adults=2, children=0)
except PackageError:
    pass  # expected
else:
    raise AssertionError("unpriced board was priced as a round trip")

# 3) packages: priced boards are honored — fare x travellers is transparent
valid_board = {
    "currency": "INR",
    "best": [{"price": 8000,
              "legs": [{"dep_code": "BOM"}, {"arr_code": "BOM"}]}],
    "others": [], "selected": [], "trip": {"origin": "BOM", "destination": "PNQ"},
}
out = build_packages(valid_board, hotel, 50000, nights=5, adults=2, children=0)
assert out["packages"][0]["breakdown"]["flight"] == 16000, out["packages"][0]
assert out["fare_per_traveller"] == 8000, out

print("OK")
