# Flights.py  (shared by build_flight_artifacts.py and the Flask service)
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from torch import nn

MODEL_DIR = Path(__file__).resolve().parent


class FlightNetwork(nn.Module):
    def __init__(self):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(37, 256),
            nn.ReLU(),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Linear(256, 1)
            # nn.ReLU(),
            # nn.Linear(64,1)
        )

    def forward(self, x):
        return self.network(x)


def load_artifacts(weights=MODEL_DIR / "flight_price_model_02.pth",
                   scaler_path=MODEL_DIR / "flight_scaler.pkl",
                   meta_path=MODEL_DIR / "flight_meta.json"):
    with open(meta_path) as f:
        meta = json.load(f)
    scaler = joblib.load(scaler_path)

    model = FlightNetwork()
    model.load_state_dict(torch.load(weights, map_location="cpu"))
    model.eval()
    return model, scaler, meta


def preprocess(rows, meta, scaler):
    """Same steps as the training notebook, applied to raw search dicts.

    Expected keys per row: airline, source_city, departure_time, stops,
    arrival_time, destination_city, class, duration, days_left
    """
    X = pd.DataFrame(rows)

    # canonicalize: case-insensitive, spaces accepted in place of underscores,
    # then map onto the exact training category labels
    lookup = {
        c: {v.lower(): v for v in meta["options"][c]}
        for c in meta["cat_cols"]
    }
    unknown = []
    for c in meta["cat_cols"]:
        norm = X[c].astype(str).str.strip().str.lower().str.replace(" ", "_")
        X[c] = norm.map(lookup[c])
        bad = X[c].isna()
        if bad.any():
            for v in sorted(set(norm[bad])):
                unknown.append(f"{c}='{v}'")

    if unknown:
        raise ValueError(
            "invalid values: " + ", ".join(unknown)
            + f"; valid options: {json.dumps(meta['options'])}"
        )

    X[meta["num_cols"]] = X[meta["num_cols"]].apply(pd.to_numeric, errors="coerce")

    X = pd.get_dummies(X, columns=meta["cat_cols"], dtype="float32")
    X = X.reindex(columns=meta["columns"], fill_value=0)  # exact training column order

    return scaler.transform(X).astype(np.float32)


def predict_price(model, scaler, meta, rows):
    x = torch.tensor(preprocess(rows, meta, scaler), dtype=torch.float32)
    with torch.no_grad():
        price = model(x).squeeze(1).numpy()
    return price
