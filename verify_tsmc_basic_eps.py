
import json
from pathlib import Path

RAW_PATH = Path("data/fundamentals_raw_test.json")

# Official TSMC FY2025 basic EPS, NT dollars per share.
OFFICIAL_FY2025_BASIC_EPS = 66.26

FY2025_DATES = [
    "2025-03-31",
    "2025-06-30",
    "2025-09-30",
    "2025-12-31",
]

TOLERANCE = 0.005


def main():
    if not RAW_PATH.exists():
        print(f"[FAIL] Missing {RAW_PATH}")
        return 1

    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    rows = []

    def walk(obj, dataset=""):
        if isinstance(obj, dict):
            if {"date", "type", "value"}.issubset(obj):
                rows.append({
                    "dataset": dataset,
                    "date": str(obj["date"]),
                    "type": str(obj["type"]),
                    "value": obj["value"],
                })
                return

            for key, value in obj.items():
                next_dataset = (
                    key if key.startswith("TaiwanStock") else dataset
                )
                walk(value, next_dataset)

        elif isinstance(obj, list):
            for item in obj:
                walk(item, dataset)

    walk(raw)

    values = {}
    for date in FY2025_DATES:
        matches = [
            row for row in rows
            if row["dataset"] == "TaiwanStockFinancialStatements"
            and row["type"] == "EPS"
            and row["date"] == date
        ]

        if not matches:
            print(f"[FAIL] Missing EPS record: {date}")
            return 1

        values[date] = float(matches[0]["value"])

    print("=" * 60)
    print("TSMC FY2025 Basic EPS Verification - TEST ONLY")
    print("=" * 60)

    for date in FY2025_DATES:
        print(f"{date}: FinMind basic EPS = {values[date]:.2f}")

    quarterly_sum = sum(values.values())
    difference = quarterly_sum - OFFICIAL_FY2025_BASIC_EPS

    print("-" * 60)
    print(f"FinMind quarterly basic EPS sum: {quarterly_sum:.2f}")
    print(f"Official annual basic EPS:       {OFFICIAL_FY2025_BASIC_EPS:.2f}")
    print(f"Difference:                      {difference:+.2f}")

    # Compare values rounded to two decimal places.
    passed = round(quarterly_sum, 2) == round(
        OFFICIAL_FY2025_BASIC_EPS, 2
    )

    print("Result:", "PASS" if passed else "REVIEW REQUIRED")
    print()
    print("Important:")
    print("- This checks FY2025 basic EPS, not diluted EPS.")
    print("- The official Q4 diluted EPS is 19.50; do not use it")
    print("  as the Q4 basic EPS reference.")
    print("- Passing this check does not prove all TTM periods")
    print("  are free of share-basis adjustments.")
    print("- No production files were modified.")

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
