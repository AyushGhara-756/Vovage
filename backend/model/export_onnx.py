# One-off: export flight_price_model_02.pth to ONNX and verify.
# Mirrors the new ONNX cells in backend/notebooks/flights.ipynb.
import sys
from pathlib import Path

MODEL = Path("backend/model")
sys.path.insert(0, str(MODEL))

import numpy as np
import torch
from Flights import FlightNetwork, load_artifacts

model, scaler, meta = load_artifacts()
onnx_path = MODEL / "flight_price_model_02.onnx"

torch.onnx.export(
    model.cpu(),
    torch.zeros(1, len(meta["columns"])),
    str(onnx_path),
    input_names=["features"],
    output_names=["price"],
    dynamic_axes={"features": {0: "batch"}, "price": {0: "batch"}},
    opset_version=17,
)
print("exported", onnx_path)

import onnxruntime as ort

sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

# real feature rows through the serving preprocess, compared torch vs onnx
rows = [
    {"airline": "AirAsia", "source_city": "Bangalore", "departure_time": "Morning",
     "stops": "zero", "arrival_time": "Afternoon", "destination_city": "Chennai",
     "class": "Economy", "duration": 90, "days_left": 50},
    {"airline": "Vistara", "source_city": "Delhi", "departure_time": "Morning",
     "stops": "zero", "arrival_time": "Afternoon", "destination_city": "Mumbai",
     "class": "Business", "duration": 135, "days_left": 10},
]
from Flights import preprocess
x = preprocess(rows, meta, scaler)
onnx_out = sess.run(None, {"features": x})[0].squeeze(1)
with torch.no_grad():
    ref = model(torch.tensor(x, dtype=torch.float32)).squeeze(1).numpy()
diff = np.abs(onnx_out - ref).max()
print("torch:", ref.round(1), "\nonnx :", onnx_out.round(1), "\nmax abs diff:", diff)
assert np.allclose(onnx_out, ref, atol=1e-3), "ONNX drift too large"
print("OK — ONNX matches PyTorch")
