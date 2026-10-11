
import json
import math
import sys
from pathlib import Path

REPORT_PATH = Path("data/fundamentals_calculation_test.json")

REQUIRED_METRICS = [
    "EPS_TTM_candidate",
    "ROE_TTM_candidate_percent",
    "Revenue_YoY_percent",
    "PER",
    "OperatingCashFlow_TTM_candidate",
]

# These calculations are still candidates, not production-verified data.
UNVERIFIED_METRICS = {
    "EPS_TTM_candidate",
    "ROE_TTM_candidate_percent",
    "OperatingCashFlow_TTM_candidate",
}


def fail(message):
    print(f"[FAIL] {message}")


def warn(message):
    print(f"[WARN] {message}")


def passed(message):
    print(f"[PASS] {message}")


def main():
    print("=" * 60)
    print("Fundamentals Data Quality Check")
    print("=" * 60)

    if not REPORT_PATH.exists():
        fail(f"Report not found: {REPORT_PATH}")
        print("Run calculate_fundamentals.py first.")
        return 1

    try:
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Cannot parse JSON: {exc}")
        return 1

    if not isinstance(report, dict):
        fail("Report root must be a JSON object.")
        return 1

    passed("Calculation report is valid JSON.")

    if report.get("testOnly") is True:
        passed("Report is explicitly marked testOnly.")
    else:
        warn("testOnly is not true. Confirm this is test data only.")

    metrics = report.get("metrics")
    if not isinstance(metrics, dict):
        fail("Missing or invalid 'metrics' object.")
        return 1

    errors = 0
    warnings = 0

    for name in REQUIRED_METRICS:
        if name not in metrics:
            fail(f"Missing metric: {name}")
            errors += 1
            continue

        metric = metrics[name]
        if not isinstance(metric, dict):
            fail(f"{name}: metric must be an object.")
            errors += 1
            continue

        passed(f"{name}: present.")

        # Find a numeric result, supporting the report's known field names.
        candidates = [
            metric.get("value"),
            metric.get("valuePercent"),
        ]
        numeric_values = [
            value for value in candidates
            if isinstance(value, (int, float))
            and not isinstance(value, bool)
        ]

        if not numeric_values:
            fail(f"{name}: no numeric value/valuePercent found.")
            errors += 1
            continue

        value = numeric_values[0]
        if not math.isfinite(value):
            fail(f"{name}: result is not finite.")
            errors += 1
            continue

        passed(f"{name}: numeric result = {value}")

        status = str(metric.get("status", ""))
        if name in UNVERIFIED_METRICS:
            if "verified" in status.lower() and "unverified" not in status.lower():
                warn(
                    f"{name}: status says '{status}'. "
                    "Confirm the period basis before accepting it."
                )
                warnings += 1
            else:
                passed(f"{name}: remains a candidate pending verification.")

        if name == "PER" and value <= 0:
            warn("PER is not positive; investigate the source record.")
            warnings += 1

        if name == "Revenue_YoY_percent":
            if not metric.get("latestPeriod"):
                warn("Revenue YoY has no latestPeriod.")
                warnings += 1
            if metric.get("priorYearRevenue") in (None, 0):
                warn("Revenue YoY has missing/zero prior-year revenue.")
                warnings += 1

    print("-" * 60)
    print(f"Errors:   {errors}")
    print(f"Warnings: {warnings}")

    if errors:
        print("RESULT: FAIL")
        return 1

    print("RESULT: PASS (structure/numeric checks only)")
    print(
        "NOTE: PASS does not prove accounting-period definitions "
        "or financial values are correct."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
