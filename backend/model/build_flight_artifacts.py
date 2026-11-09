# build_flight_artifacts.py
# Run once. Replicates flights.ipynb's preprocessing exactly and saves the
# missing serving artifacts (scaler + meta) around flight_price_model_01.pth.
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.preprocessing import StandardScaler

import torch

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "Clean_Dataset.csv"
WEIGHTS = Path(__file__).resolve().parent / "flight_price_model_01.pth"

CAT_COLS = ["airline", "source_city", "departure_time", "stops",
            "arrival_time", "destination_city", "class"]

df = pd.read_csv(CSV_PATH)  # includes 'price'

# ---------- same prep as the training notebook ----------
y = df["price"]
X = df.drop(columns=["price", "Unnamed: 0", "flight"])

X = pd.get_dummies(X, columns=CAT_COLS, dtype="float32")
X["duration"] = X["duration"].astype("float32")
X["days_left"] = X["days_left"].astype("float32")

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)   # scaler was never saved by the notebook
X_test_s = scaler.transform(X_test)

# ---------- verify the saved weights reproduce the notebook's metrics ----------
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from Flights import FlightNetwork  # noqa: E402

model = FlightNetwork()
model.load_state_dict(torch.load(WEIGHTS, map_location="cpu"))
model.eval()

Xte = torch.tensor(np.asarray(X_test_s, dtype=np.float32), dtype=torch.float32)
with torch.no_grad():
    pred = model(Xte).squeeze(1).numpy()

true = y_test.to_numpy()
print(f"[check] features: {X.shape[1]} | params: {sum(p.numel() for p in model.parameters()):,}")
print(f"[check] R2 {r2_score(true, pred):.4f} | MAE {mean_absolute_error(true, pred):,.2f}")

# ---------- save serving artifacts ----------
meta = {
    "columns": X.columns.tolist(),
    "cat_cols": CAT_COLS,
    "options": {c: sorted(df[c].astype(str).unique().tolist()) for c in CAT_COLS},
    "num_cols": ["duration", "days_left"],
    "duration_min": float(df["duration"].min()),
    "duration_max": float(df["duration"].max()),
    "days_left_min": int(df["days_left"].min()),
    "days_left_max": int(df["days_left"].max()),
}

joblib.dump(scaler, Path(__file__).resolve().parent / "flight_scaler.pkl")
with open(Path(__file__).resolve().parent / "flight_meta.json", "w") as f:
    json.dump(meta, f, indent=2)

print("saved flight_scaler.pkl + flight_meta.json")
