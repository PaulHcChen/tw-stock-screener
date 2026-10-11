
import json
import re
from pathlib import Path

RAW_PATH = Path("data/fundamentals_raw_test.json")

KEYWORDS = (
    "eps",
    "incomeaftertax",
    "netincome",
    "equity",
    "cashflowsfromoperatingactivities",
    "netcashinflowfromoperatingactivities",
)


def normalize(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def walk(obj, dataset="", records=None):
    if records is None:
        records = []

    if isinstance(obj, dict):
        # Identify a financial data record.
        if "date" in obj and "type" in obj and "value" in obj:
            records.append({
                "dataset": dataset,
                "date": str(obj.get("date", "")),
                "type": str(obj.get("type", "")),
                "value": obj.get("value"),
                "origin_name": str(obj.get("origin_name", "")),
            })
            return records

        for key, value in obj.items():
            next_dataset = (
                str(key)
                if any(word in normalize(key) for word in (
                    "financialstatements",
                    "balancesheet",
                    "cashflowsstatement",
                ))
                else dataset
            )
            walk(value, next_dataset, records)

    elif isinstance(obj, list):
        for item in obj:
            walk(item, dataset, records)

    return records


def main():
    print("=" * 70)
    print("Fundamentals Period Audit - TEST ONLY")
    print("=" * 70)

    if not RAW_PATH.exists():
        print(f"[FAIL] Missing raw data: {RAW_PATH}")
        return 1

    try:
        raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[FAIL] Cannot read JSON: {exc}")
        return 1

    records = walk(raw)

    if not records:
        print("[FAIL] No financial records found in expected format.")
        print("Please inspect the raw JSON structure before changing formulas.")
        return 1

    selected = []
    for row in records:
        typ = normalize(row["type"])
        if any(keyword in typ for keyword in KEYWORDS):
            selected.append(row)

    selected.sort(
        key=lambda row: (
            row["dataset"],
            row["type"],
            row["date"],
        )
    )

    if not selected:
        print("[FAIL] No matching EPS/income/equity/cash-flow records.")
        return 1

    print(f"Matching records: {len(selected)}")
    print("Values are printed as provided by the source; no conversion.")
    print("-" * 70)

    for row in selected:
        print(
            f'{row["dataset"] or "(dataset unknown)"} | '
            f'{row["date"]} | {row["type"]} | '
            f'{row["value"]} | {row["origin_name"]}'
        )

    print("-" * 70)
    print("AUDIT OUTPUT ONLY: no formulas or source data were modified.")
    print("Check quarterly versus year-to-date definitions before recalculating.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
