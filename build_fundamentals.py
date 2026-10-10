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
OUTPUT_FILE = DATA_DIR / "fundamentals.json"

API_URL = "https://api.finmindtrade.com/api/v4/data"
TZ_TAIPEI = timezone(timedelta(hours=8))

# 本階段只驗證台積電，不計算正式指標。
TEST_CODE = "2330"
START_DATE = "2025-01-01"

DATASETS = [
    "TaiwanStockFinancialStatements",
    "TaiwanStockBalanceSheet",
    "TaiwanStockCashFlowsStatement",
    "TaiwanStockMonthRevenue",
    "TaiwanStockPER",
]

# 這些是本階段要確認的欄位類型。
TARGET_TYPES = {
    "TaiwanStockFinancialStatements": [
        "EPS",
        "IncomeAfterTaxes",
        "IncomeAfterTaxesFromContinuingOperation",
    ],
    "TaiwanStockBalanceSheet": [
        "EquityAttributableToOwnersOfParent",
    ],
    "TaiwanStockCashFlowsStatement": [
        "經營活動現金流",
    ],
}


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
        message = str(result.get("msg", ""))[:200]
        raise RuntimeError(
            f"{dataset}: API status "
            f"{result.get('status')}; {message}"
        )

    rows = result.get("data")
    if not isinstance(rows, list):
        raise RuntimeError(
            f"{dataset}: unexpected response format"
        )

    return rows


def select_samples(dataset, rows):
    if dataset in TARGET_TYPES:
        target_types = TARGET_TYPES[dataset]
        matched = [
            row for row in rows
            if str(row.get("type", "")) in target_types
        ]
        if matched:
            return matched[-5:]
        return rows[-5:]

    if dataset == "TaiwanStockMonthRevenue":
        return rows[-3:]

    if dataset == "TaiwanStockPER":
        return rows[-3:]

    return rows[-3:]


def main():
    token = os.environ.get("FINMIND_API_TOKEN", "").strip()

    if not token:
        print("ERROR: FINMIND_API_TOKEN is missing.")
        return 1

    diagnostic = {
        "source": "FinMind",
        "updatedAt": now_text(),
        "schemaVersion": 1,
        "testOnly": True,
        "stockCode": TEST_CODE,
        "startDate": START_DATE,
        "datasets": {},
        "note": (
            "Schema validation only. "
            "No fundamental metrics calculated."
        ),
    }

    try:
        for dataset in DATASETS:
            rows = request_dataset(dataset, token)

            if rows:
                fields = sorted({
                    key
                    for row in rows
                    for key in row.keys()
                })
            else:
                fields = []

            samples = select_samples(dataset, rows)

            diagnostic["datasets"][dataset] = {
                "rowCount": len(rows),
                "fields": fields,
                "samples": samples,
            }

            print("")
            print("=" * 65)
            print(f"DATASET: {dataset}")
            print(f"ROW COUNT: {len(rows)}")
            print(f"FIELDS: {', '.join(fields)}")
            print("SAMPLES:")

            if samples:
                print(json.dumps(
                    samples,
                    ensure_ascii=False,
                    indent=2,
                ))
            else:
                print(
                    "No matching sample rows. "
                    "Check returned field names and type values."
                )

            print(f"PASS: {dataset}")

    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = OUTPUT_FILE.with_suffix(".json.tmp")

    try:
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(
                diagnostic,
                file,
                ensure_ascii=False,
                indent=2,
            )
            file.write("\n")

        temp_path.replace(OUTPUT_FILE)

    except Exception as exc:
        print(
            "ERROR: Cannot save diagnostic output "
            f"({type(exc).__name__})."
        )
        return 1

    print("")
    print("PASS: All five datasets validated.")
    print("PASS: Diagnostic output saved to data/fundamentals.json")
    print("NOTE: This file is test data, not production fundamentals.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
