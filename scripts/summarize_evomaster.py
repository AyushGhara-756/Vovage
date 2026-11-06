import csv
import json
from pathlib import Path

STATISTICS_FILE = Path("statistics.csv")
SCHEMA_FILE = Path("openapi.json")

KEYS = [
    "generatedTests",
    "evaluatedTests",
    "evaluatedActions",
    "elapsedSeconds",
    "endpoints",
    "covered2xx",
    "coveredTargets",
    "errors5xx",
    "distinct500Faults",
    "potentialFaults",
    "potentialFaultCategories",
    "potentialFaultsSummary",
]


def main():
    print("## EvoMaster results")
    print()

    if SCHEMA_FILE.exists():
        schema = json.loads(SCHEMA_FILE.read_text())
        print(f"Noir discovered **{len(schema.get('paths', {}))}** paths.")
        print()

    if not STATISTICS_FILE.exists():
        print("No `statistics.csv` was produced. Check the EvoMaster step logs.")
        return

    with STATISTICS_FILE.open(newline="") as handle:
        row = next(csv.DictReader(handle))

    print("| Metric | Value |")
    print("| --- | --- |")
    for key in KEYS:
        if key in row:
            value = row[key] or "-"
            print(f"| `{key}` | {value} |")


if __name__ == "__main__":
    main()
