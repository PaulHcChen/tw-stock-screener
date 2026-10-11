
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent
INPUT_FILE = ROOT / "data" / "fundamentals.json"
OUTPUT_FILE = ROOT / "data" / "fundamentals_calculation_test.json"
TZ = timezone(timedelta(hours=8))


def quarter_key(date_text):
    year, month, _ = map(int, date_text.split("-"))
    quarter = (month - 1) // 3 + 1
    return year, quarter


def trailing_four_sum(values_by_date):
    dates = sorted(values_by_date)
    if len(dates) < 4:
        return None

    last_four = dates[-4:]
    quarters = [quarter_key(d) for d in last_four]

    # 確認是連續四季，避免資料缺漏時仍計算。
    for i in range(1, 4):
        py, pq = quarters[i - 1]
        y, q = quarters[i]
        expected = (py + 1, 1) if pq == 4 else (py, pq + 1)
        if (y, q) != expected:
            return None

    return sum(float(values_by_date[d]) for d in last_four)


def calculate_roe_ttm(net_income, equity):
    income_dates = sorted(net_income)
    equity_dates = sorted(equity)

    if len(income_dates) < 4 or len(equity_dates) < 5:
        return None

    last_four_income_dates = income_dates[-4:]
    latest_date = last_four_income_dates[-1]

    if latest_date not in equity:
        return None

    previous_equity_dates = [
        d for d in equity_dates if d < last_four_income_dates[0]
    ]
    if not previous_equity_dates:
        return None

    beginning_equity = equity[previous_equity_dates[-1]]
    ending_equity = equity[latest_date]

    if beginning_equity <= 0 or ending_equity <= 0:
        return None

    income_sum = sum(
        float(net_income[d]) for d in last_four_income_dates
    )
    average_equity = (beginning_equity + ending_equity) / 2

    return income_sum / average_equity * 100


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            "Missing data/fundamentals.json. "
            "Run the diagnostic workflow first."
        )

    raw = json.loads(INPUT_FILE.read_text(encoding="utf-8"))

    if raw.get("testOnly") is not True:
        raise RuntimeError(
            "Expected diagnostic test data; refusing to process "
            "an unexpected input file."
        )

    data = raw.get("datasets", {})

    # The earlier validation workflow prints results but does not
    # save raw datasets into this file. Stop safely if they are absent.
    required = [
        "TaiwanStockFinancialStatements",
        "TaiwanStockBalanceSheet",
        "TaiwanStockCashFlowsStatement",
        "TaiwanStockMonthRevenue",
        "TaiwanStockPER",
    ]
    if not all(name in data for name in required):
        raise RuntimeError(
            "Current fundamentals.json contains only API test metadata, "
            "not the raw diagnostic datasets. No calculations were made. "
            "Next step: adapt validate_fundamentals.py to save the raw "
            "dataset records to a separate diagnostic JSON file."
        )

    # If raw dataset rows are present, the calculations can be added
    # after confirming the dataset period basis and unit conventions.
    print("Raw datasets found. Ready for calculation validation.")
    print("No production data was modified.")


if __name__ == "__main__":
    main()
