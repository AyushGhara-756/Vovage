# hotel_pipeline.py  (shared by rebuild_artifacts.py and app.py)
import json
import joblib
import numpy as np
import pandas as pd
import torch
from torch import nn

MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December']


class BhoirNetwork(nn.Module):
    def __init__(self, in_features):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(in_features, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.1),

            nn.Linear(256, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.1),

            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),

            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1)
        )

    def forward(self, x):
        return self.network(x)


def load_artifacts(weights="backend/model/hotel_price.pth", scaler_path="backend/model/hotel_scaler.pkl", meta_path="backend/model/hotel_meta.json"):
    with open(meta_path) as f:
        meta = json.load(f)
    scaler = joblib.load(scaler_path)

    model = BhoirNetwork(len(meta["columns"]))
    model.load_state_dict(torch.load(weights, map_location="cpu"))
    model.eval()  # IMPORTANT: turns off Dropout, uses BatchNorm running stats
    return model, scaler, meta


def preprocess(rows, meta, scaler):
    """Same steps as the training notebook, applied to raw booking dicts."""
    X = pd.DataFrame(rows)

    # anything not sent gets its training default (median / most common value)
    for c, d in meta["defaults"].items():
        if c not in X.columns:
            X[c] = d
    X = X[list(meta["defaults"].keys())].copy()

    X['children'] = X['children'].fillna(0)
    X['total_nights'] = X['stays_in_weekend_nights'] + X['stays_in_week_nights']
    X['total_guests'] = X['adults'] + X['children'] + X['babies']

    for c in ['agent', 'company']:
        X[c] = X[c].fillna(0).astype(int).astype(str)

    m = X['arrival_date_month'].map({k: i for i, k in enumerate(MONTHS)})
    X['month_sin'] = np.sin(2 * np.pi * m / 12)
    X['month_cos'] = np.cos(2 * np.pi * m / 12)

    for c in meta["cat_cols"]:
        X[c] = X[c].astype(str)
        X[c] = X[c].where(X[c].isin(meta["top_values"][c]), 'other')

    X = pd.get_dummies(X, columns=meta["cat_cols"], dtype='float32')
    X = X.reindex(columns=meta["columns"], fill_value=0)  # exact training column order

    return scaler.transform(X).astype(np.float32)


def predict_adr(model, scaler, meta, rows):
    x = torch.tensor(preprocess(rows, meta, scaler), dtype=torch.float32)
    with torch.no_grad():
        out = model(x) * meta["y_std"] + meta["y_mean"]
        price = torch.expm1(out).squeeze(1).numpy()
    return np.clip(price, 0, None)