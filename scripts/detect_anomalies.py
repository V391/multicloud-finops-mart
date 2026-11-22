"""Run the anomaly check on the mart and compare it with two common rules.

Reads main.mart_daily_usage (usage only) and main.fct_daily_cost (all charges, to
show what happens when the check runs on net cost instead). Writes
outputs/anomalies.csv, outputs/rule_comparison.csv and docs/anomaly_ec2.png.
"""
import sys
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from finops.anomaly import day_over_day, fixed_threshold, rolling_forecast  # noqa: E402

DB = ROOT / "warehouse.duckdb"
OUT = ROOT / "outputs"
DOCS = ROOT / "docs"
SERIES = [
    ("AWS", "Amazon Elastic Compute Cloud"),
    ("AWS", "AmazonCloudWatch"),
    ("AWS", "Amazon Relational Database Service"),
    ("AWS", "Elastic Load Balancing"),
    ("AWS", "Amazon Simple Storage Service"),
]
WINDOW, K = 7, 3.5
MIN_EXCESS = 1.0       # dollars beyond the interval edge before a break is worth an alert
DOD_PCT = 0.5          # day-over-day rule: +50%
STATIC_MULT = 1.5      # static rule: 1.5x the first week's average daily cost


def main() -> None:
    OUT.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB), read_only=True)
    usage = con.execute("select * from main.mart_daily_usage order by charge_date").df()
    net = con.execute(
        "select charge_date, sum(billed_cost) as net_cost from main.fct_daily_cost "
        "where provider = 'AWS' group by 1 order by 1"
    ).df()

    flagged, comparison, plotted = [], [], {}
    for provider, service in SERIES:
        s = usage[(usage.provider == provider) & (usage.service_name == service)].reset_index(drop=True)
        y = s.usage_cost.to_numpy()
        fc = rolling_forecast(y, window=WINDOW, k=K)
        # Materiality: ignore breaks worth less than MIN_EXCESS dollars in the day.
        fc["is_anomaly"] = fc.is_anomaly & (fc.excess.abs() >= MIN_EXCESS)
        fc.insert(0, "charge_date", s.charge_date)
        fc.insert(1, "service_name", service)
        scored = fc.index >= WINDOW  # only days every rule can score
        static_limit = STATIC_MULT * y[:WINDOW].mean()
        st = fixed_threshold(y, static_limit)
        dod = day_over_day(y, DOD_PCT)
        comparison.append({
            "service_name": service,
            "days_scored": int(scored.sum()),
            "month_usage": round(float(y.sum()), 2),
            "forecast_flags": int(fc.is_anomaly[scored].sum()),
            "static_limit": round(float(static_limit), 2),
            "static_flags": int(st[scored].sum()),
            "day_over_day_flags": int(dod[scored].sum()),
        })
        flagged.append(fc[fc.is_anomaly])
        plotted[service] = (fc, static_limit)

    plot_panels([
        ("EC2", *plotted["Amazon Elastic Compute Cloud"]),
        ("CloudWatch", *plotted["AmazonCloudWatch"]),
    ])
    anomalies = pd.concat(flagged, ignore_index=True)
    anomalies.round(2).to_csv(OUT / "anomalies.csv", index=False)
    comp = pd.DataFrame(comparison)
    comp.to_csv(OUT / "rule_comparison.csv", index=False)

    neg_days = int((net.net_cost < 0).sum())
    pd.DataFrame([{"aws_days": len(net), "aws_days_with_negative_net_cost": neg_days}]).to_csv(
        OUT / "net_cost_check.csv", index=False)

    print(comp.to_string(index=False))
    print(f"\nAWS days with negative net cost (credits included): {neg_days} of {len(net)}")
    print("\nFlagged days:")
    print(anomalies[["charge_date", "service_name", "actual", "expected", "upper", "direction", "excess"]]
          .round(2).to_string(index=False))


def plot_panels(panels) -> None:
    fig, axes = plt.subplots(1, len(panels), figsize=(11, 4.2), dpi=150, sharex=True)
    for ax, (name, fc, static_limit) in zip(axes, panels):
        d = pd.to_datetime(fc.charge_date)
        static_hits = int((fc.actual[7:] > static_limit).sum())
        ax.fill_between(d, fc.lower.clip(lower=0.01), fc.upper, color="#3ECF8E", alpha=0.2,
                        label="Forecast band")
        ax.plot(d, fc.expected, color="#249361", lw=1.1, ls="--", label="Forecast")
        ax.plot(d, fc.actual.clip(lower=0.01), color="#1c1c1c", lw=1.5, marker="o", ms=2.5, label="Actual")
        ax.axhline(static_limit, color="#D97757", lw=1.3, ls=":",
                   label=f"Static limit ${static_limit:,.2f} ({static_hits} alerts)")
        hit = fc[fc.is_anomaly]
        ax.scatter(pd.to_datetime(hit.charge_date), hit.actual, s=110, facecolors="none", edgecolors="#d6336c",
                   lw=2, zorder=5, label=f"Forecast flag ({len(hit)})")
        ax.set_yscale("log")
        ax.set_title(f"AWS {name}: daily usage cost (log scale)", loc="left", fontsize=10.5)
        ax.set_ylabel("USD per day")
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(fontsize=7.2, frameon=False, loc="upper left")
    fig.suptitle("FOCUS sample, Sep 2024. Usage only (credits excluded).", x=0.01, ha="left", fontsize=8.5,
                 color="#555")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(DOCS / "anomaly_check.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
