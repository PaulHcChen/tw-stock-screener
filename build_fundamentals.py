
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_FILE = DATA_DIR / "fundamentals.json"

API_URL = "https://api.finmindtrade.com/api/v4/data"
TZ_TAIPEI = timezone(timedelta(hours=8))


def now_text():
    return datetime.now(TZ_TAIPEI).isoformat(timespec="seconds")


def request_dataset(dataset, code, token):
    params = {
        "dataset": dataset,
        "data_id": code,
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "tw-stock-screener",
        },
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    if result.get("status") != 200:
        raise RuntimeError(f"FinMind API error: {dataset}")

    if not isinstance(result.get("data"), list):
        raise RuntimeError(f"Unexpected response: {dataset}")

    return result["data"]


def main():
    token = os.environ.get("FINMIND_API_TOKEN", "").strip()

    if not token:
        print("ERROR: FINMIND_API_TOKEN is missing.")
        return 1

    # 第一輪只測試一檔股票，避免大量 API 請求。
    code = "2330"
    datasets = [
        "TaiwanStockFinancialStatements",
        "TaiwanStockBalanceSheet",
        "TaiwanStockCashFlowsStatement",
        "TaiwanStockMonthRevenue",
        "TaiwanStockPER",
    ]

    results = {}

    try:
        for dataset in datasets:
            rows = request_dataset(dataset, code, token)
            results[dataset] = {
                "ok": True,
                "rowCount": len(rows),
            }
            print(f"PASS: {dataset}, rows={len(rows)}")

    except Exception as exc:
        # 不輸出網址、Token 或完整例外內容。
        print(f"ERROR: API test failed ({type(exc).__name__}).")
        return 1

    output = {
        "source": "FinMind",
        "updatedAt": now_text(),
        "schemaVersion": 1,
        "testOnly": True,
        "stockCode": code,
        "datasetChecks": results,
        "note": "API connectivity test only; metrics not calculated.",
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = OUTPUT_FILE.with_suffix(".json.tmp")

    try:
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(output, file, ensure_ascii=False, indent=2)
            file.write("\n")
        temp_path.replace(OUTPUT_FILE)
    except Exception as exc:
        print(f"ERROR: Cannot save output ({type(exc).__name__}).")
        return 1

    print("PASS: Test output saved to data/fundamentals.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
