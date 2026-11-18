# One-off: export hotel_price.pth to ONNX and verify.
# Mirrors the flights ONNX export (backend/notebooks/flights.ipynb) for the
# hotel ADR model. The y_std/y_mean rescale and expm1 are baked into the
# exported graph so the served output is the final ADR in both backends.
import json
import sys
from pathlib import Path

MODEL = Path("backend/model")
sys.path.insert(0, str(MODEL))

import numpy as np
import torch
from Hotels import BhoirNetwork, preprocess, load_artifacts

meta = json.load(open(MODEL / "hotel_meta.json"))
net = BhoirNetwork(len(meta["columns"]))
net.load_state_dict(torch.load(MODEL / "hotel_price.pth", map_location="cpu"))
net.eval()  # dropout off, BatchNorm running stats — same as serving


class Serving(torch.nn.Module):
    """network output -> final ADR (rescale + expm1 baked in)."""

    def __init__(self):
        super().__init__()
        self.net = net
        self.y_std = float(meta["y_std"])
        self.y_mean = float(meta["y_mean"])

    def forward(self, x):
        out = self.net(x) * self.y_std + self.y_mean
        return torch.expm1(out)


wrapper = Serving().eval()
onnx_path = MODEL / "hotel_price.onnx"

torch.onnx.export(
    wrapper,
    torch.zeros(2, len(meta["columns"])),
    str(onnx_path),
    input_names=["features"],
    output_names=["adr"],
    dynamic_axes={"features": {0: "batch"}, "adr": {0: "batch"}},
    opset_version=18,
)
print("exported", onnx_path)

# ---- verify: torch path vs onnx path on realistic rows ------------------
import joblib
import onnxruntime as ort

scaler = joblib.load(MODEL / "hotel_scaler.pkl")
sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

rows = [
    {"hotel": "City Hotel", "arrival_date_year": 2016, "arrival_date_month": "August",
     "arrival_date_week_number": 27, "arrival_date_day_of_month": 16,
     "stays_in_weekend_nights": 1, "stays_in_week_nights": 2, "adults": 2},
    {"hotel": "Resort Hotel", "arrival_date_year": 2017, "arrival_date_month": "December",
     "arrival_date_week_number": 49, "arrival_date_day_of_month": 28,
     "stays_in_weekend_nights": 2, "stays_in_week_nights": 4, "adults": 3},
]
x = preprocess(rows, meta, scaler)

onnx_out = sess.run(None, {"features": x})[0].squeeze(1)
with torch.no_grad():
    ref = wrapper(torch.tensor(x, dtype=torch.float32)).squeeze(1).numpy()

print("torch:", ref.round(1), "\nonnx :", onnx_out.round(1), "\nmax abs diff:", np.abs(onnx_out - ref).max())
assert np.allclose(onnx_out, ref, atol=1e-3), "ONNX drift too large"
print("OK — ONNX matches PyTorch")
