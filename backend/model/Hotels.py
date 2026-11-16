# hotel_pipeline.py  (shared by rebuild_artifacts.py and app.py)
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December']


class HotelNetwork:
    """Serving wrapper: ONNX runtime when the export exists (serverless
    friendly — onnxruntime is ~50 MB vs torch's ~500 MB), PyTorch otherwise.
    Both paths return the FINAL ADR (log-space rescale + expm1 applied)."""

    def __init__(self, weights="backend/model/hotel_price.pth",
                 onnx_path=Path(__file__).resolve().parent / "hotel_price.onnx",
                 in_features=None, y_std=None, y_mean=None):
        if Path(onnx_path).exists():
            import onnxruntime as ort
            self.sess = ort.InferenceSession(
                str(onnx_path), providers=["CPUExecutionProvider"])
            self.torch_model = None
        else:
            import torch
            from torch import nn

            class _Net(nn.Module):
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

            net = _Net(in_features)
            net.load_state_dict(torch.load(weights, map_location="cpu"))
            net.eval()

            self._y_std, self._y_mean = float(y_std), float(y_mean)
            self._torch = torch
            self.torch_model = net
            self.sess = None

    def predict(self, features):
        """features: 2-D float array of scaled feature rows -> 1-D ADR."""
        if self.sess is not None:
            # the graph already applies y_std/y_mean rescale + expm1
            return self.sess.run(
                None, {"features": features.astype(np.float32)})[0].squeeze(1)
        with self._torch.no_grad():
            out = self.torch_model(
                self._torch.tensor(features, dtype=self._torch.float32)
            ) * self._y_std + self._y_mean
            return self._torch.expm1(out).squeeze(1).numpy()


MODEL_DIR = Path(__file__).resolve().parent


def load_artifacts(weights=MODEL_DIR / "hotel_price.pth", scaler_path=MODEL_DIR / "hotel_scaler.pkl", meta_path=MODEL_DIR / "hotel_meta.json"):
    with open(meta_path) as f:
        meta = json.load(f)
    scaler = joblib.load(scaler_path)

    model = HotelNetwork(
        weights=weights,
        in_features=len(meta["columns"]),
        y_std=meta["y_std"],
        y_mean=meta["y_mean"],
    )
    return model, scaler, meta  # IMPORTANT: wrapper keeps Dropout off / BN stats


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
    x = preprocess(rows, meta, scaler)
    return np.clip(model.predict(x), 0, None)