
import json
from pathlib import Path

RAW_PATH = Path("data/fundamentals_raw_test.json")

# TSMC official quarterly EPS, NT dollars per share.
OFFICIAL_EPS = {
    "2025-09-30": 17.44,
    "2025-12-31": 19.50,
    "2026-03-31": 22.08,
    "2026-06-30": 27.25,
}

# Official FY2025 EPS, for an independent cross-check.
OFFICIAL_FY2025_EPS = 66.25


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

    print("=" * 65)
    print("TSMC EPS TTM Official Cross-check - TEST ONLY")
    print("=" * 65)

    finmind = {}
    for date in OFFICIAL_EPS:
        matches = [
            row for row in rows
            if row["dataset"] == "TaiwanStockFinancialStatements"
            and row["type"] == "EPS"
            and row["date"] == date
        ]

        if not matches:
            print(f"[FAIL] Missing FinMind EPS for {date}")
            return 1

        finmind[date] = float(matches[0]["value"])

    official_ttm = 0.0
    finmind_ttm = 0.0
    errors = 0

    for date, official_value in OFFICIAL_EPS.items():
        actual = finmind[date]
        difference = actual - official_value

        official_ttm += official_value
        finmind_ttm += actual

        result = "PASS" if abs(difference) < 0.005 else "DIFFERENCE"

        print(f"\nQuarter: {date}")
        print(f"  FinMind EPS: {actual:.2f}")
        print(f"  Official EPS: {official_value:.2f}")
        print(f"  Difference: {difference:+.2f}")
        print(f"  Result: {result}")

        if result != "PASS":
            errors += 1

    print("\n" + "-" * 65)
    print(f"FinMind four-quarter EPS sum: {finmind_ttm:.2f}")
    print(f"Official four-quarter EPS sum: {official_ttm:.2f}")
    print(f"Difference: {finmind_ttm - official_ttm:+.2f}")

    fy2025_dates = [
        "2025-03-31",
        "2025-06-30",
        "2025-09-30",
        "2025-12-31",
    ]
    fy2025_values = {}

    for date in fy2025_dates:
        matches = [
            row for row in rows
            if row["dataset"] == "TaiwanStockFinancialStatements"
            and row["type"] == "EPS"
            and row["date"] == date
        ]
        if matches:
            fy2025_values[date] = float(matches[0]["value"])

    if len(fy2025_values) == 4:
        finmind_fy2025 = sum(fy2025_values.values())
        print(f"\nFinMind FY2025 quarterly EPS sum: {finmind_fy2025:.2f}")
        print(f"Official FY2025 EPS: {OFFICIAL_FY2025_EPS:.2f}")
        print(
            "FY2025 difference: "
            f"{finmind_fy2025 - OFFICIAL_FY2025_EPS:+.2f}"
        )
    else:
        print("\n[WARN] Incomplete FY2025 quarterly EPS records.")

    print("\nNo source data or production formulas were modified.")
    print(
        "NOTE: EPS sums are diagnostic only; official quarterly and "
        "annual EPS may differ due to rounding or share-basis adjustments."
    )
    print(f"Quarters with differences: {errors}")
    print("RESULT:", "REVIEW REQUIRED" if errors else "PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
