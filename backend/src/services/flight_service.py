try:
    from ...model.Flights import load_artifacts, predict_price
except ImportError:  # service-root layout: backend/ sits on sys.path
    from model.Flights import load_artifacts, predict_price

REQUIRED = [
    "airline", "source_city", "departure_time", "stops", "arrival_time",
    "destination_city", "class", "duration", "days_left",
]


class FlightService:
    def __init__(self):
        self.model, self.scaler, self.meta = load_artifacts()

    def predict(self, rows):
        """rows: list of raw search dicts (or a single dict)."""
        if isinstance(rows, dict):
            rows = [rows]

        if not all(isinstance(r, dict) for r in rows):
            raise ValueError("each record must be a JSON object of search fields")

        missing = sorted(
            {c for r in rows for c in REQUIRED if c not in r}
        )
        if missing:
            raise ValueError(f"missing fields: {missing}")

        return predict_price(self.model, self.scaler, self.meta, rows)


def predict(rows):
    return flight_service.predict(rows)


flight_service = FlightService()
