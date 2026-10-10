#!/usr/bin/env python3
"""Build the latest 60 trading days of TWSE-listed daily stock prices."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "stock_history.json"
BASE_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
TARGET_DAYS = 60
INITIAL_LOOKBACK_DAYS = 180
RECENT_REFRESH_DAYS = 10
TAIPEI = ZoneInfo("Asia/Taipei")


def number(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("--", "")
    if not text or text in {"-", "—", "除權", "除息"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fetch_day(day):
    params = urllib.parse.urlencode({
        "date": day.strftime("%Y%m%d"),
        "type": "ALLBUT0999",
        "response": "json",
    })
    url = f"{BASE_URL}?{params}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; TWStockScreener/1.0)",
            "Accept": "application/json,text/plain,*/*",
        },
    )

    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"Request failed for {day.isoformat()}: {last_error}")

    # TWSE can return HTTP 200 for non-trading days; check stat, not HTTP alone.
    if payload.get("stat") != "OK":
        return []

    tables = payload.get("tables") or []
    table = next(
        (
            item for item in tables
            if isinstance(item.get("fields"), list)
            and "證券代號" in item["fields"]
            and "證券名稱" in item["fields"]
            and "收盤價" in item["fields"]
            and "成交股數" in item["fields"]
        ),
        None,
    )
    if table is None:
        # Successful API status but an unexpected schema should stop the workflow.
        raise RuntimeError(
            f"Could not find the stock quote table for {day.isoformat()}"
        )

    fields = table["fields"]
    indexes = {name: fields.index(name) for name in
               ("證券代號", "證券名稱", "收盤價", "成交股數")}
    rows = []
    for raw in table.get("data", []):
        try:
            code = str(raw[indexes["證券代號"]]).strip()
            name = str(raw[indexes["證券名稱"]]).strip()
            close = number(raw[indexes["收盤價"]])
            volume = number(raw[indexes["成交股數"]])
        except (IndexError, TypeError):
            continue

        if not code or not close or close <= 0 or volume is None or volume < 0:
            continue

        rows.append({
            "date": day.isoformat(),
            "code": code,
            "name": name,
            "close": close,
            "volumeShares": int(volume),
        })
    return rows


def load_existing():
    if not OUTPUT.exists():
        return {}
    try:
        with OUTPUT.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("source") != "TWSE_MI_INDEX" or not isinstance(payload.get("records"), list):
            raise RuntimeError("Existing history file has an unexpected format")
        records = {}
        for row in payload["records"]:
            if all(key in row for key in ("date", "code", "name", "close", "volumeShares")):
                records[(row["date"], row["code"])] = row
        return records
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Existing history JSON is invalid: {exc}") from exc


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    existing = load_existing()
    today = datetime.now(TAIPEI).date()

    existing_dates = sorted({key[0] for key in existing}, reverse=True)
    if len(existing_dates) >= TARGET_DAYS:
        # Routine runs refresh the last 10 calendar days to catch missed runs
        # and corrections without re-requesting the entire history every day.
        days_to_fetch = [
            today - timedelta(days=offset)
            for offset in range(RECENT_REFRESH_DAYS)
        ]
    else:
        # Initial bootstrap: go back far enough to collect 60 actual trading days.
        days_to_fetch = [
            today - timedelta(days=offset)
            for offset in range(INITIAL_LOOKBACK_DAYS)
        ]

    collected = dict(existing)
    fetched_dates = set()
    for day in days_to_fetch:
        # Do not waste requests on weekends. Weekday holidays are handled by stat.
        if day.weekday() >= 5:
            continue
        rows = fetch_day(day)
        if rows:
            fetched_dates.add(day.isoformat())
            for row in rows:
                collected[(row["date"], row["code"])] = row
        time.sleep(0.25)

        all_dates = sorted({key[0] for key in collected}, reverse=True)
        if len(all_dates) >= TARGET_DAYS and len(existing_dates) < TARGET_DAYS:
            break

    all_dates = sorted({key[0] for key in collected}, reverse=True)
    if len(all_dates) < TARGET_DAYS:
        raise RuntimeError(
            f"Only {len(all_dates)} trading dates available; need {TARGET_DAYS}. "
            "No history file was written."
        )

    keep_dates = set(all_dates[:TARGET_DAYS])
    final_records = [
        row for (trade_date, _), row in collected.items()
        if trade_date in keep_dates
    ]
    final_records.sort(key=lambda row: (row["date"], row["code"]))

    output = {
        "source": "TWSE_MI_INDEX",
        "updatedAt": datetime.now(TAIPEI).isoformat(),
        "latestDate": max(keep_dates),
        "tradingDates": sorted(keep_dates),
        "tradingDateCount": len(keep_dates),
        "recordCount": len(final_records),
        "records": final_records,
    }

    temp = OUTPUT.with_suffix(".json.tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")
    temp.replace(OUTPUT)

    print("History build successful")
    print("Latest trading date:", output["latestDate"])
    print("Trading dates:", output["tradingDateCount"])
    print("Stock-day records:", output["recordCount"])
    print("Saved to:", OUTPUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
