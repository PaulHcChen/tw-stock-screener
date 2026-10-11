
import json
import math
from pathlib import Path

RAW_PATH = Path("data/fundamentals_raw_test.json")
OLD_PATH = Path("data/fundamentals_calculation_test.json")
OUT_PATH = Path("data/fundamentals_calculation_comparison_test.json")

INCOME_DS = "TaiwanStockFinancialStatements"
BALANCE_DS = "TaiwanStockBalanceSheet"
CASH_DS = "TaiwanStockCashFlowsStatement"


def load_records(obj):
    records = []

    def walk(value, dataset=""):
        if isinstance(value, dict):
            if {"date", "type", "value"}.issubset(value):
                records.append({
                    "dataset": dataset,
                    "date": str(value["date"]),
                    "type": str(value["type"]),
                    "value": value["value"],
                    "stock_id": str(value.get("stock_id", "2330")),
                })
                return

            for key, child in value.items():
                next_dataset = key if key.startswith("TaiwanStock") else dataset
                walk(child, next_dataset)

        elif isinstance(value, list):
            for child in value:
                walk(child, dataset)

    walk(obj)
    return records


def get_series(records, dataset, item_type):
    result = {}

    for row in records:
        if row["dataset"] != dataset:
            continue
        if row["type"] != item_type:
            continue
        if row["stock_id"] != "2330":
            continue

        try:
            value = float(row["value"])
        except (TypeError, ValueError):
            continue

        if math.isfinite(value):
            result[row["date"]] = value

    return result


def latest_four_contiguous(values):
    dates = sorted(values)
    if len(dates) < 4:
        raise ValueError("少於四季資料，無法計算 TTM。")

    dates = dates[-4:]

    # Expected calendar quarter-end dates.
    expected = {
        "03-31", "06-30", "09-30", "12-31"
    }

    if any(date[5:] not in expected for date in dates):
        raise ValueError("最近四筆資料包含非季末日期。")

    for i in range(1, len(dates)):
        year1, month1 = map(int, dates[i - 1][:7].split("-"))
        year2, month2 = map(int, dates[i][:7].split("-"))

        if (year2 * 12 + month2) - (year1 * 12 + month1) != 3:
            raise ValueError("最近四季日期不連續。")

    return dates


def require_dates(values, dates, label):
    missing = [date for date in dates if date not in values]
    if missing:
        raise ValueError(f"{label} 缺少日期：{missing}")


def main():
    for path in (RAW_PATH, OLD_PATH):
        if not path.exists():
            raise FileNotFoundError(f"找不到檔案：{path}")

    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    old = json.loads(OLD_PATH.read_text(encoding="utf-8"))

    records = load_records(raw)

    eps = get_series(records, INCOME_DS, "EPS")
    net_income = get_series(records, INCOME_DS, "IncomeAfterTaxes")
    parent_profit = get_series(
        records, INCOME_DS, "EquityAttributableToOwnersOfParent"
    )
    parent_equity = get_series(
        records, BALANCE_DS, "EquityAttributableToOwnersOfParent"
    )
    ocf = get_series(
        records, CASH_DS, "CashFlowsFromOperatingActivities"
    )

    dates = latest_four_contiguous(net_income)

    for values, label in (
        (eps, "EPS"),
        (parent_profit, "歸屬母公司淨利"),
        (parent_equity, "歸屬母公司業主權益"),
        (ocf, "營業現金流"),
    ):
        require_dates(values, dates, label)

    # EPS: retain the sum as a candidate only.
    eps_ttm = sum(eps[d] for d in dates)

    # ROE: parent-attributable net income / average parent equity.
    opening_dates = sorted(d for d in parent_equity if d < dates[0])
    if not opening_dates:
        raise ValueError("找不到 TTM 期間開始前的股東權益。")

    opening_date = opening_dates[-1]
    closing_date = dates[-1]
    average_equity = (
        parent_equity[opening_date] + parent_equity[closing_date]
    ) / 2

    parent_profit_ttm = sum(parent_profit[d] for d in dates)
    roe_corrected = parent_profit_ttm / average_equity * 100

    # Convert year-to-date cash flow to individual quarter values.
    ocf_quarterly = {}
    for date in sorted(ocf):
        if date.endswith("-03-31"):
            ocf_quarterly[date] = ocf[date]
        else:
            previous_dates = [d for d in ocf if d < date]
            if not previous_dates:
                continue
            previous_date = max(previous_dates)

            # Only subtract the immediately preceding quarter.
            year1, month1 = map(int, previous_date[:7].split("-"))
            year2, month2 = map(int, date[:7].split("-"))
            if (year2 * 12 + month2) - (year1 * 12 + month1) != 3:
                continue

            ocf_quarterly[date] = ocf[date] - ocf[previous_date]

    require_dates(ocf_quarterly, dates, "單季營業現金流")
    ocf_ttm = sum(ocf_quarterly[d] for d in dates)

    old_metrics = old.get("metrics", {})

    def old_value(name, field="value"):
        metric = old_metrics.get(name, {})
        value = metric.get(field)
        return value if isinstance(value, (int, float)) else None

    old_eps = old_value("EPS_TTM_candidate")
    old_roe = old_value("ROE_TTM_candidate_percent")
    old_ocf = old_value("OperatingCashFlow_TTM_candidate")

    report = {
        "testOnly": True,
        "stockId": "2330",
        "quarterDates": dates,
        "metrics": {
            "EPS_TTM_candidate": {
                "old": old_eps,
                "recalculated": round(eps_ttm, 4),
                "difference": (
                    round(eps_ttm - old_eps, 4)
                    if old_eps is not None else None
                ),
                "status": "share_basis_requires_verification",
            },
            "ROE_TTM_parent_candidate_percent": {
                "old": old_roe,
                "recalculated": round(roe_corrected, 4),
                "difference": (
                    round(roe_corrected - old_roe, 4)
                    if old_roe is not None else None
                ),
                "openingEquityDate": opening_date,
                "closingEquityDate": closing_date,
                "netIncomeBasis": "Income attributable to parent",
                "equityBasis": "Equity attributable to owners of parent",
                "status": "calculated_period_basis_review_required",
            },
            "OperatingCashFlow_TTM_candidate": {
                "old": old_ocf,
                "recalculated": round(ocf_ttm, 2),
                "difference": (
                    round(ocf_ttm - old_ocf, 2)
                    if old_ocf is not None else None
                ),
                "quarterlyValues": {
                    d: ocf_quarterly[d] for d in dates
                },
                "status": "cumulative_basis_assumption_requires_verification",
            },
        },
        "notes": [
            "Test-only report; not for production screening.",
            "EPS TTM sum is not fully verified for share-basis adjustments.",
            "OCF quarterly conversion assumes cumulative year-to-date values.",
            "ROE uses parent-attributable profit and average parent equity.",
        ],
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 60)
    print("Fundamentals Calculation Comparison - TEST ONLY")
    print("=" * 60)
    print(f"Quarter dates: {dates}")

    for name, metric in report["metrics"].items():
        print(f"\n{name}")
        print(f"  Old:           {metric['old']}")
        print(f"  Recalculated:  {metric['recalculated']}")
        print(f"  Difference:    {metric['difference']}")
        print(f"  Status:        {metric['status']}")

    print(f"\nReport saved: {OUT_PATH}")
    print("No production data or original calculation file was modified.")


if __name__ == "__main__":
    main()
