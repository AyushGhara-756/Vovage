# rebuild_artifacts.py
# Run once, on CPU. Needs: hotel_booking.csv + hotel_price.pth in the same folder.
import json
import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_absolute_error

from Hotels import BhoirNetwork, MONTHS, preprocess, predict_adr

CSV_PATH = "hotel_booking.csv"
WEIGHTS = "hotel_price.pth"

# IMPORTANT: fresh read of the FULL csv. Do NOT use the 14-column df from cell 6 of the notebook,
# the saved weights were trained on the full one (297 features).
df = pd.read_csv(CSV_PATH)

# ---------- same prep as the training cell ----------
target = 'adr'
df_h = df[(df[target] > 0) & (df[target] < 1000)].copy()

leaky = ['reservation_status', 'reservation_status_date']
Xh = df_h.drop(columns=[target] + [c for c in leaky if c in df_h.columns])
yh = df_h[target]

raw = Xh.copy()  # untouched copy, used for defaults + the serving-path check

Xh['total_nights'] = Xh['stays_in_weekend_nights'] + Xh['stays_in_week_nights']
Xh['total_guests'] = Xh['adults'] + Xh['children'].fillna(0) + Xh['babies']

for c in ['agent', 'company']:
    if c in Xh.columns:
        Xh[c] = Xh[c].fillna(0).astype(int).astype(str)

Xh['children'] = Xh['children'].fillna(0)

m = Xh['arrival_date_month'].map({k: i for i, k in enumerate(MONTHS)})
Xh['month_sin'] = np.sin(2 * np.pi * m / 12)
Xh['month_cos'] = np.cos(2 * np.pi * m / 12)

cat_cols = Xh.select_dtypes(exclude='number').columns.tolist()
top_values = {}
for c in cat_cols:
    top = Xh[c].value_counts().index[:30]
    top_values[c] = [str(v) for v in top]
    Xh[c] = Xh[c].where(Xh[c].isin(top), 'other')

Xh = pd.get_dummies(Xh, columns=cat_cols, dtype='float32')

Xh_train, Xh_test, yh_train, yh_test = train_test_split(Xh, yh, test_size=0.2, random_state=42)

scaler = StandardScaler()
Xh_train_s = scaler.fit_transform(Xh_train)
Xh_test_s = scaler.transform(Xh_test)

y_log = np.log1p(yh_train)
y_mean = float(y_log.mean())
y_std = float(y_log.std())

# ---------- load the saved weights ----------
state = torch.load(WEIGHTS, map_location="cpu")
saved_in = state["network.0.weight"].shape[1]
print(f"weights expect {saved_in} features | rebuilt {Xh.shape[1]} features")

if saved_in != Xh.shape[1]:
    raise SystemExit("Feature count mismatch: this csv/prep is not what the model was trained on.")

model = BhoirNetwork(saved_in)
model.load_state_dict(state)
model.eval()

# ---------- defaults for fields the API caller doesn't send ----------
ID_COLS = ['name', 'email', 'phone-number', 'credit_card']  # identity columns -> always 'other'
defaults = {}
for c in raw.columns:
    if c in ['agent', 'company']:
        defaults[c] = 0
    elif pd.api.types.is_numeric_dtype(raw[c]):
        defaults[c] = float(raw[c].median()) if not np.isnan(raw[c].median()) else 0.0
    elif c in ID_COLS:
        defaults[c] = 'other'
    else:
        defaults[c] = str(raw[c].mode().iloc[0])

meta = {
    "columns": Xh.columns.tolist(),
    "cat_cols": cat_cols,
    "top_values": top_values,
    "y_mean": y_mean,
    "y_std": y_std,
    "defaults": defaults,
}

# ---------- check 1: notebook-style path ----------
Xte = torch.tensor(np.asarray(Xh_test_s, dtype=np.float32), dtype=torch.float32)
with torch.no_grad():
    pred_nb = torch.expm1(model(Xte) * y_std + y_mean).squeeze(1).numpy()
true = yh_test.to_numpy()
print(f"[notebook path] R2 {r2_score(true, pred_nb):.4f} | MAE {mean_absolute_error(true, pred_nb):,.2f}")

# ---------- check 2: the exact function Flask will use, on raw rows ----------
raw_rows = raw.loc[Xh_test.index].to_dict(orient="records")
pred_api = predict_adr(model, scaler, meta, raw_rows)
print(f"[flask path]    R2 {r2_score(true, pred_api):.4f} | MAE {mean_absolute_error(true, pred_api):,.2f}")
print("max |difference| between the two paths:", float(np.abs(pred_nb - pred_api).max()))

# ---------- save ----------
joblib.dump(scaler, "hotel_scaler.pkl")
with open("hotel_meta.json", "w") as f:
    json.dump(meta, f)
print("saved hotel_scaler.pkl + hotel_meta.json")