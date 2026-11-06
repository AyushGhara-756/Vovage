#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PORT=6050
MAX_TIME="${MAX_TIME:-120s}"
OUTPUT_DIR="generated_tests"

BACKEND_PID=""

cleanup() {
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "==> Generating OpenAPI schema with Noir"
if ! noir scan backend -f oas3 --no-log --no-color --no-spinner > openapi.json 2> noir.log; then
  echo "Noir failed. Log:"
  cat noir.log
  exit 1
fi

python - <<'PY'
import json
from pathlib import Path

schema = json.loads(Path("openapi.json").read_text())
paths = schema.get("paths") or {}
if not paths:
    raise SystemExit("Noir generated an empty OpenAPI schema")

print(f"Noir discovered {len(paths)} paths:")
for path in sorted(paths):
    methods = ", ".join(sorted(method.upper() for method in paths[path]))
    print(f"  {path} [{methods}]")
PY

echo "==> Starting Flask backend on 127.0.0.1:${PORT}"
python -m backend > backend.log 2>&1 &
BACKEND_PID=$!

ready=""
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${PORT}/api/test/" > /dev/null 2>&1; then
    ready="1"
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Backend exited during startup. Log:"
    cat backend.log
    exit 1
  fi
  sleep 1
done

if [[ -z "$ready" ]]; then
  echo "Backend did not become ready within 30s. Log:"
  cat backend.log
  exit 1
fi

echo "==> Running EvoMaster (maxTime=${MAX_TIME})"
evomaster \
  --configPath em.yaml \
  --maxTime "$MAX_TIME" \
  | tee evomaster.log

echo "==> Checking EvoMaster fault statistics"
python - <<'PY'
import csv
from pathlib import Path

path = Path("statistics.csv")
if not path.exists():
    raise SystemExit("statistics.csv was not produced; is writeStatistics enabled?")

with path.open(newline="") as handle:
    row = next(csv.DictReader(handle))

faults = int(row.get("distinct500Faults") or 0)
print(f"distinct500Faults={faults}")
print(f"potentialFaults={row.get('potentialFaults', '0')}")
if faults > 0:
    raise SystemExit(f"EvoMaster found {faults} distinct 500 fault(s)")
PY

echo "==> Running generated EvoMaster tests"
python -m unittest discover -s "$OUTPUT_DIR" -p 'EvoMaster*Test*.py' -v

echo "==> Done"
