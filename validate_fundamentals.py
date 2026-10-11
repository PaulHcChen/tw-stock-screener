
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

API_URL = "https://api.finmindtrade.com/api/v4/data"
CODE = "2330"
START_DATE = "2024-01-01"
TZ = timezone(timedelta(hours=8))


def fetch(dataset, token):
    params = {
        "dataset": dataset,
        "data_id": CODE,
        "start_date": START_DATE,
        "token": token,
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "tw-stock-screener"},
    )

    with urllib.request.urlopen(request, timeout=45) as response:
        result = json.loads(response.read().decode("utf-8"))

    if result.get("status") != 200:
        raise RuntimeError(
            f"{dataset}: API status {result.get('status')}"
        )

    return result["data"]


def main():
    token = os.environ.get("FINMIND_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("FINMIND_API_TOKEN is missing")

    financial = fetch("TaiwanStockFinancialStatements", token)
    balance = fetch("TaiwanStockBalanceSheet", token)
    cashflow = fetch("TaiwanStockCashFlowsStatement", token)
    revenue = fetch("TaiwanStockMonthRevenue", token)
    per = fetch("TaiwanStockPER", token)

    # 僅保留計算所需的明確項目。
    eps = [
        r for r in financial
        if r.get("type") == "EPS"
    ]
    net_income = [
        r for r in financial
        if r.get("type") == "IncomeAfterTaxes"
    ]
    equity = [
        r for r in balance
        if r.get("type") == "EquityAttributableToOwnersOfParent"
    ]
    ocf = [
        r for r in cashflow
        if r.get("type") == "CashFlowsFromOperatingActivities"
    ]

    # 同一財報日期只取一筆，不將重複代碼加總。
    def by_date(rows):
        result = {}
        for row in rows:
            result[row["date"]] = row["value"]
        return dict(sorted(result.items()))

    eps_by_date = by_date(eps)
    income_by_date = by_date(net_income)
    equity_by_date = by_date(equity)
    ocf_cumulative_by_date = by_date(ocf)

    # 現金流先列出原始值與相鄰期差額。
    # 差額僅是候選單季值，仍須確認來源為年初至今累計。
    ocf_dates = sorted(ocf_cumulative_by_date)
    ocf_quarter_candidates = {}

    for i, date in enumerate(ocf_dates):
        current = ocf_cumulative_by_date[date]
        if date.endswith("-03-31"):
            ocf_quarter_candidates[date] = current
        elif i > 0:
            previous = ocf_cumulative_by_date[ocf_dates[i - 1]]
            ocf_quarter_candidates[date] = current - previous

    latest_revenue = sorted(
        revenue,
        key=lambda r: (
            r.get("revenue_year", 0),
            r.get("revenue_month", 0),
        ),
    )

    latest_per = sorted(per, key=lambda r: r["date"])

    report = {
        "source": "FinMind",
        "stockCode": CODE,
        "generatedAt": datetime.now(TZ).isoformat(),
        "testOnly": True,
        "rawQuarterlyCandidates": {
            "EPS_by_date": eps_by_date,
            "netIncome_by_date": income_by_date,
            "parentEquity_by_date": equity_by_date,
            "operatingCashFlowRaw_by_date": ocf_cumulative_by_date,
            "operatingCashFlowQuarterCandidates_by_date":
                ocf_quarter_candidates,
        },
        "latestRevenueRecords": latest_revenue[-14:],
        "latestPERRecords": latest_per[-5:],
        "validationNotes": [
            "Verify EPS period basis before calculating TTM.",
            "Verify net income period basis before calculating ROE.",
            "Verify cash flow cumulative basis before using quarter differences.",
            "ROE requires matching four-quarter net income and beginning/end equity.",
            "Revenue YoY requires matching the same month in the prior year.",
            "Do not treat this diagnostic output as production screening data.",
        ],
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
