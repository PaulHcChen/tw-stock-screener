
import json
import math
from pathlib import Path

RAW_PATH = Path("data/fundamentals_raw_test.json")

# TSMC official 2026 Q2 consolidated report.
# Amounts are in NT dollars, not NT thousands.
OFFICIAL = {
    "EPS": 27.25,
    "IncomeAfterTaxes": 706_780_923_000,
    "EquityAttributableToOwnersOfParent": 706_561_938_000,
    "OperatingCashFlow_6M": 1_482_341_242_000,
}

TOLERANCE = {
    "EPS": 0.01,
    "IncomeAfterTaxes": 1_000_000,
    "EquityAttributableToOwnersOfParent": 1_000_000,
    "OperatingCashFlow_6M": 1_000_000,
}


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

    checks = [
        (
            "EPS",
            "TaiwanStockFinancialStatements",
            "EPS",
            "2026-06-30",
        ),
        (
            "IncomeAfterTaxes",
            "TaiwanStockFinancialStatements",
            "IncomeAfterTaxes",
            "2026-06-30",
        ),
        (
            "EquityAttributableToOwnersOfParent",
            "TaiwanStockFinancialStatements",
            "EquityAttributableToOwnersOfParent",
            "2026-06-30",
        ),
        (
            "OperatingCashFlow_6M",
            "TaiwanStockCashFlowsStatement",
            "CashFlowsFromOperatingActivities",
            "2026-06-30",
        ),
    ]

    print("=" * 65)
    print("TSMC Q2 2026 Official Data Cross-check")
    print("TEST ONLY - no production data changed")
    print("=" * 65)

    errors = 0

    for name, dataset, item_type, date in checks:
        matches = [
            row for row in rows
            if row["dataset"] == dataset
            and row["type"] == item_type
            and row["date"] == date
        ]

        if not matches:
            print(f"[FAIL] {name}: source record not found")
            errors += 1
            continue

        try:
            actual = float(matches[0]["value"])
        except (TypeError, ValueError):
            print(f"[FAIL] {name}: invalid source value")
            errors += 1
            continue

        expected = OFFICIAL[name]
        difference = actual - expected
        ok = (
            math.isfinite(actual)
            and abs(difference) <= TOLERANCE[name]
        )

        print(f"\n{name}")
        print(f"  FinMind:  {actual:,.3f}")
        print(f"  Official: {expected:,.3f}")
        print(f"  Difference: {difference:,.3f}")
        print(f"  Result: {'PASS' if ok else 'FAIL'}")

        if not ok:
            errors += 1

    print("\nNote:")
    print("- The cash-flow value is the six-month cumulative figure.")
    print("- Q2-only operating cash flow = six-month value minus Q1.")
    print("- Official quarterly ROE is annualized and is not directly")
    print("  comparable with the TTM ROE calculated by this project.")
    print("- EPS TTM still needs cross-quarter share-basis verification.")

    print(f"\nErrors: {errors}")
    print("RESULT:", "PASS" if errors == 0 else "FAIL")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
