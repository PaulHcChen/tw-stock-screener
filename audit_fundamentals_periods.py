
import json
from pathlib import Path

RAW = Path("data/fundamentals_raw_test.json")


def load_records():
    obj = json.loads(RAW.read_text(encoding="utf-8"))
    records = []

    def walk(x, dataset=""):
        if isinstance(x, dict):
            if {"date", "type", "value"}.issubset(x):
                records.append({
                    "dataset": dataset,
                    "date": str(x["date"]),
                    "type": str(x["type"]),
                    "value": x["value"],
                    "origin_name": x.get("origin_name", ""),
                })
                return
            for k, v in x.items():
                ds = k if k in {
                    "TaiwanStockFinancialStatements",
                    "TaiwanStockBalanceSheet",
                    "TaiwanStockCashFlowsStatement",
                    "TaiwanStockMonthRevenue",
                    "TaiwanStockPER",
                } else dataset
                walk(v, ds)
        elif isinstance(x, list):
            for item in x:
                walk(item, dataset)

    walk(obj)
    return records


def series(records, dataset, typ):
    return {
        r["date"]: float(r["value"])
        for r in records
        if r["dataset"] == dataset
        and r["type"] == typ
        and isinstance(r["value"], (int, float))
    }


def show_series(title, values):
    print(f"\n{title}")
    for date, value in sorted(values.items()):
        print(f"  {date}: {value:,.3f}")


def main():
    print("=" * 68)
    print("Fundamentals Period Audit - TEST ONLY")
    print("=" * 68)

    if not RAW.exists():
        print(f"[FAIL] Missing {RAW}")
        return 1

    records = load_records()
    if not records:
        print("[FAIL] No financial records found.")
        return 1

    income_ds = "TaiwanStockFinancialStatements"
    balance_ds = "TaiwanStockBalanceSheet"
    cash_ds = "TaiwanStockCashFlowsStatement"

    eps = series(records, income_ds, "EPS")
    net_income = series(records, income_ds, "IncomeAfterTaxes")
    parent_net_income = series(
        records, income_ds, "EquityAttributableToOwnersOfParent"
    )
    parent_equity = series(
        records, balance_ds, "EquityAttributableToOwnersOfParent"
    )
    total_equity = series(records, balance_ds, "Equity")
    ocf = series(records, cash_ds, "CashFlowsFromOperatingActivities")
    ocf_alt = series(
        records, cash_ds, "NetCashInflowFromOperatingActivities"
    )

    show_series("EPS (quarterly records)", eps)
    show_series("IncomeAfterTaxes", net_income)
    show_series("Net income attributable to parent", parent_net_income)
    show_series("Parent equity (balance sheet)", parent_equity)
    show_series("Total equity (balance sheet)", total_equity)
    show_series("Operating cash flow as supplied", ocf)

    print("\nQuarterly OCF differences (diagnostic only)")
    dates = sorted(ocf)
    for i, date in enumerate(dates):
        if date.endswith("-03-31"):
            quarter_value = ocf[date]
        elif i > 0:
            quarter_value = ocf[date] - ocf[dates[i - 1]]
        else:
            continue
        print(f"  {date}: {quarter_value:,.0f}")

    if ocf and ocf_alt:
        common = sorted(set(ocf) & set(ocf_alt))
        same = all(abs(ocf[d] - ocf_alt[d]) < 0.01 for d in common)
        print(
            "\nOCF aliases identical on matching dates: "
            f"{same} ({len(common)} dates)"
        )

    print("\nLatest four EPS records vs net income")
    common_dates = sorted(set(eps) & set(net_income))
    last4 = common_dates[-4:]
    print(f"  Dates: {last4}")
    if len(last4) == 4:
        print(f"  Sum of four EPS values: {sum(eps[d] for d in last4):.3f}")
        print(
            "  Sum of four net income values: "
            f"{sum(net_income[d] for d in last4):,.0f}"
        )
        print(
            "  NOTE: EPS sum is diagnostic only; share bases may differ."
        )

    print("\nROE diagnostic")
    if len(last4) == 4 and last4[0] in parent_equity:
        start_date = sorted(
            d for d in parent_equity if d < last4[0]
        )
        end_date = last4[-1]
        if start_date and end_date in parent_equity:
            start = parent_equity[start_date[-1]]
            end = parent_equity[end_date]
            avg_equity = (start + end) / 2
            profit = sum(net_income[d] for d in last4)
            parent_profit = sum(
                parent_net_income[d] for d in last4
                if d in parent_net_income
            )
            print(f"  Opening parent equity date: {start_date[-1]}")
            print(f"  Closing parent equity date: {end_date}")
            print(
                "  ROE using total net income / average parent equity: "
                f"{profit / avg_equity * 100:.3f}%"
            )
            print(
                "  ROE using parent net income / average parent equity: "
                f"{parent_profit / avg_equity * 100:.3f}%"
            )

    print("\nAUDIT ONLY: no source data or production formulas changed.")
    print("Confirm accounting definitions before accepting any candidate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
