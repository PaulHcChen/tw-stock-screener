
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_FILE = DATA_DIR / "fundamentals_raw_test.json"

API_URL = "https://api.finmindtrade.com/api/v4/data"
TZ_TAIPEI = timezone(timedelta(hours=8))

TEST_CODE = "2330"
START_DATE = "2024-01-01"

DATASETS = [
    "TaiwanStockFinancialStatements",
    "TaiwanStockBalanceSheet",
    "TaiwanStockCashFlowsStatement",
    "TaiwanStockMonthRevenue",
    "TaiwanStockPER",
]


def now_text():
    return datetime.now(TZ_TAIPEI).isoformat(timespec="seconds")


def request_dataset(dataset, token):
    params = {
        "dataset": dataset,
        "data_id": TEST_CODE,
        "start_date": START_DATE,
        "token": token,
    }

    url = API_URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "tw-stock-screener"},
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            detail = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            detail = {}
        message = str(detail.get("msg", ""))[:200]
        raise RuntimeError(
            f"{dataset}: HTTP {exc.code}; {message}"
        ) from None

    if result.get("status") != 200:
        raise RuntimeError(
            f"{dataset}: API status {result.get('status')}; "
            f"{str(result.get('msg', ''))[:200]}"
        )

    rows = result.get("data")
    if not isinstance(rows, list):
        raise RuntimeError(
            f"{dataset}: unexpected response format"
        )

    return rows


def main():
    token = os.environ.get("FINMIND_API_TOKEN", "").strip()
    if not token:
        print("ERROR: FINMIND_API_TOKEN is missing.")
        return 1

    all_data = {}

    try:
        for dataset in DATASETS:
            rows = request_dataset(dataset, token)
            all_data[dataset] = rows

            fields = sorted({
                key
                for row in rows
                for key in row.keys()
            })

            print("")
            print("=" * 65)
            print(f"DATASET: {dataset}")
            print(f"ROW COUNT: {len(rows)}")
            print(f"FIELDS: {', '.join(fields)}")

            if dataset == "TaiwanStockCashFlowsStatement":
                operating = [
                    row for row in rows
                    if row.get("type")
                    == "CashFlowsFromOperatingActivities"
                ]
                print(
                    "OPERATING CASH FLOW ROWS: "
                    f"{len(operating)}"
                )
                print(json.dumps(
                    operating[-8:],
                    ensure_ascii=False,
                    indent=2,
                ))
            else:
                print("SAMPLES:")
                print(json.dumps(
                    rows[-3:],
                    ensure_ascii=False,
                    indent=2,
                ))

            print(f"PASS: {dataset}")

    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    output = {
        "source": "FinMind",
        "stockCode": TEST_CODE,
        "startDate": START_DATE,
        "generatedAt": now_text(),
        "testOnly": True,
        "datasets": all_data,
        "note": (
            "Raw diagnostic data for calculation validation only. "
            "Not production screening data."
        ),
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = OUTPUT_FILE.with_suffix(".json.tmp")

    try:
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(
                output,
                file,
                ensure_ascii=False,
                indent=2,
            )
            file.write("\n")

        temp_path.replace(OUTPUT_FILE)

    except Exception as exc:
        print(
            "ERROR: Cannot save raw data "
            f"({type(exc).__name__})."
        )
        return 1

    print("")
    print("PASS: All five datasets retrieved.")
    print(
        "PASS: Raw test data saved to "
        "data/fundamentals_raw_test.json"
    )
    print("NOTE: No production data was modified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
