
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent
INPUT_FILE = ROOT / "data" / "fundamentals_raw_test.json"
OUTPUT_FILE = ROOT / "data" / "fundamentals_calculation_test.json"
TZ = timezone(timedelta(hours=8))


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def quarter_key(date_text):
    year, month, _ = map(int, date_text.split("-"))
    return year, (month - 1) // 3 + 1


def latest_by_date(rows, value_key="value"):
    result = {}
    for row in rows:
        date_text = row.get("date")
        value = row.get(value_key)
        if date_text and value is not None:
            result[date_text] = float(value)
    return dict(sorted(result.items()))


def last_four_contiguous(values):
    dates = sorted(values)
    if len(dates) < 4:
        return None

    selected = dates[-4:]
    quarters = [quarter_key(date_text) for date_text in selected]

    for i in range(1, 4):
        py, pq = quarters[i - 1]
        y, q = quarters[i]
        expected = (py + 1, 1) if pq == 4 else (py, pq + 1)
        if (y, q) != expected:
            return None

    return selected


def ttm_sum(values):
    dates = last_four_contiguous(values)
    if not dates:
        return None
    return sum(values[date_text] for date_text in dates)


def yoy_revenue(rows):
    valid = [
        row for row in rows
        if row.get("revenue_year") is not None
        and row.get("revenue_month") is not None
        and row.get("revenue") is not None
    ]
    if not valid:
        return None

    latest = max(
        valid,
        key=lambda row: (
            int(row["revenue_year"]),
            int(row["revenue_month"]),
        ),
    )

    previous_year = int(latest["revenue_year"]) - 1
    month = int(latest["revenue_month"])

    previous = next(
        (
            row for row in valid
            if int(row["revenue_year"]) == previous_year
            and int(row["revenue_month"]) == month
        ),
        None,
    )

    if previous is None or float(previous["revenue"]) == 0:
        return {
            "latestPeriod": (
                f'{latest["revenue_year"]}-'
                f'{int(latest["revenue_month"]):02d}'
            ),
            "valuePercent": None,
            "status": "missing_prior_year_month",
        }

    growth = (
        float(latest["revenue"]) / float(previous["revenue"]) - 1
    ) * 100

    return {
        "latestPeriod": (
            f'{latest["revenue_year"]}-'
            f'{int(latest["revenue_month"]):02d}'
        ),
        "latestRevenue": float(latest["revenue"]),
        "priorYearRevenue": float(previous["revenue"]),
        "valuePercent": round(growth, 4),
        "status": "calculated",
    }


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            "Missing data/fundamentals_raw_test.json. "
            "Run Validate Fundamentals first."
        )

    raw = json.loads(INPUT_FILE.read_text(encoding="utf-8"))

    if raw.get("testOnly") is not True:
        raise RuntimeError(
            "Input is not marked as test data; stopping safely."
        )

    datasets = raw.get("datasets", {})

    financial = datasets.get("TaiwanStockFinancialStatements", [])
    balance = datasets.get("TaiwanStockBalanceSheet", [])
    cashflows = datasets.get("TaiwanStockCashFlowsStatement", [])
    revenues = datasets.get("TaiwanStockMonthRevenue", [])
    per_rows = datasets.get("TaiwanStockPER", [])

    eps = latest_by_date([
        row for row in financial if row.get("type") == "EPS"
    ])
    net_income = latest_by_date([
        row for row in financial
        if row.get("type") == "IncomeAfterTaxes"
    ])
    equity = latest_by_date([
        row for row in balance
        if row.get("type") == "EquityAttributableToOwnersOfParent"
    ])
    ocf = latest_by_date([
        row for row in cashflows
        if row.get("type") == "CashFlowsFromOperatingActivities"
    ])

    # 只做候選計算，不宣稱來源期間口徑已獲確認。
    eps_ttm = ttm_sum(eps)
    net_income_ttm = ttm_sum(net_income)

    roe = None
    income_dates = last_four_contiguous(net_income)
    if income_dates:
        first_date = income_dates[0]
        last_date = income_dates[-1]
        previous_equity_dates = [
            d for d in equity if d < first_date
        ]
        if previous_equity_dates and last_date in equity:
            beginning = equity[previous_equity_dates[-1]]
            ending = equity[last_date]
            if beginning > 0 and ending > 0:
                average_equity = (beginning + ending) / 2
                roe = net_income_ttm / average_equity * 100

    # 假設現金流是年初至今累計值，計算單季候選值。
    ocf_quarter_candidates = {}
    for date_text in sorted(ocf):
        year, quarter = quarter_key(date_text)
        if quarter == 1:
            ocf_quarter_candidates[date_text] = ocf[date_text]
        else:
            previous_quarter = (
                f"{year}-03-31" if quarter == 2 else
                f"{year}-06-30" if quarter == 3 else
                f"{year}-09-30"
            )
            previous_value = ocf.get(previous_quarter)
            if previous_value is not None:
                ocf_quarter_candidates[date_text] = (
                    ocf[date_text] - previous_value
                )

    ocf_ttm_candidate = ttm_sum(ocf_quarter_candidates)

    valid_per = [
        row for row in per_rows
        if row.get("PER") is not None and float(row["PER"]) > 0
    ]
    latest_per = max(valid_per, key=lambda row: row["date"]) if valid_per else None

    report = {
        "source": "FinMind",
        "stockCode": raw.get("stockCode", "2330"),
        "generatedAt": datetime.now(TZ).isoformat(),
        "testOnly": True,
        "metrics": {
            "EPS_TTM_candidate": {
                "value": round(eps_ttm, 4) if eps_ttm is not None else None,
                "status": "period_basis_requires_verification",
            },
            "ROE_TTM_candidate_percent": {
                "value": round(roe, 4) if roe is not None else None,
                "status": "period_basis_requires_verification",
            },
            "Revenue_YoY_percent": yoy_revenue(revenues),
            "PER": {
                "date": latest_per.get("date") if latest_per else None,
                "value": float(latest_per["PER"]) if latest_per else None,
                "status": "latest_available_record",
            },
            "OperatingCashFlow_TTM_candidate": {
                "value": (
                    round(ocf_ttm_candidate, 2)
                    if ocf_ttm_candidate is not None else None
                ),
                "status": "cumulative_basis_requires_verification",
            },
        },
        "diagnostics": {
            "EPS_by_date": eps,
            "netIncome_by_date": net_income,
            "parentEquity_by_date": equity,
            "operatingCashFlowRaw_by_date": ocf,
            "operatingCashFlowQuarterCandidates_by_date":
                ocf_quarter_candidates,
        },
        "note": (
            "Diagnostic calculations only. Do not use for production "
            "screening until period basis and definitions are verified."
        ),
    }

    OUTPUT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nPASS: Calculation test saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
