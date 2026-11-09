from ...model.Flights import FlightNetwork
import torch
from pathlib import Path

class FlightService:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        model_path = Path(__file__).resolve().parent.parent.parent / "model" / "flight_price_model_01.pth"

        self.model = FlightNetwork()
        self.model.load_state_dict(
            torch.load(model_path, map_location=self.device)
        )

        self.model.to(self.device)
        self.model.eval()

    def predict(self, features):
        if len(features) != 37:
            raise ValueError("Expected 37 features")

        x = torch.tensor(
            features,
            dtype=torch.float32
        ).reshape(1, 37).to(self.device)

        with torch.no_grad():
            prediction = self.model(x)

        return float(prediction.item())


def predict(features):
    return flight_service.predict(features)


flight_service = FlightService()