"""Compute the numbers quoted in the README from the built warehouse.

Every figure in the README findings comes from outputs/findings.json, which this
script writes. Nothing is typed in by hand.
"""
import json
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "warehouse.duckdb"
OUT = ROOT / "outputs"

# Off-hours window used for the dev scheduling estimate. Assumption: dev compute is
# only needed Mon-Fri 08:00-20:00 UTC. The sample has no time zone per team.
WORK_DAYS = (1, 2, 3, 4, 5)          # ISO day of week, Mon=1
WORK_HOURS = range(8, 20)


def one(con, sql):
    return con.execute(sql).fetchone()


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    f = {}

    # 1. Reconciliation
    rec = con.execute("select * from main.mart_reconciliation order by provider, charge_category").df()
    f["reconciliation"] = {
        "source_rows": int(rec.source_rows.sum()),
        "mart_rows": int(rec.mart_rows.sum()),
        "max_abs_billed_diff": float(rec.billed_diff.abs().max()),
        "max_abs_effective_diff": float(rec.effective_diff.abs().max()),
    }
    aws_u = one(con, """
        select sum(billed_cost), sum(effective_cost),
               count(*) filter (where effective_cost <> 0),
               count(*) filter (where effective_cost <> 0 and effective_cost = round(effective_cost)),
               count(*) filter (where billed_cost <> 0),
               count(*) filter (where billed_cost <> 0 and billed_cost = round(billed_cost))
        from main.stg_focus__charges where provider = 'AWS' and charge_category = 'usage'""")
    f["effective_cost_check"] = {
        "aws_usage_billed": round(aws_u[0], 2),
        "aws_usage_effective": round(aws_u[1], 2),
        "aws_rows_nonzero_effective": aws_u[2],
        "aws_rows_nonzero_effective_whole_dollars": aws_u[3],
        "aws_rows_nonzero_billed": aws_u[4],
        "aws_rows_nonzero_billed_whole_dollars": aws_u[5],
    }

    # 2. Credits
    cr = one(con, """
        select sum(billed_cost) filter (where charge_category = 'credit'),
               sum(billed_cost) filter (where charge_category = 'usage')
        from main.fct_daily_cost where provider = 'AWS'""")
    net = pd.read_csv(OUT / "net_cost_check.csv").iloc[0]
    f["credits"] = {
        "aws_credits": round(cr[0], 2),
        "aws_usage": round(cr[1], 2),
        "credits_share_of_usage": round(-cr[0] / cr[1], 4),
        "aws_days_negative_net": int(net.aws_days_with_negative_net_cost),
        "aws_days": int(net.aws_days),
    }

    # 3. Run rate
    rr = one(con, """
        with d as (select charge_date, sum(usage_cost) c from main.mart_daily_usage
                   where provider = 'AWS' group by 1),
             e as (select charge_date, usage_cost c from main.mart_daily_usage
                   where provider = 'AWS' and service_name = 'Amazon Elastic Compute Cloud')
        select (select avg(c) from (select c from d order by charge_date limit 7)),
               (select avg(c) from (select c from d order by charge_date desc limit 7)),
               (select sum(c) from e) / (select sum(c) from d),
               (select avg(c) from (select c from e order by charge_date limit 7)),
               (select avg(c) from (select c from e order by charge_date desc limit 7))""")
    f["run_rate"] = {
        "aws_usage_first7_avg": round(rr[0], 2),
        "aws_usage_last7_avg": round(rr[1], 2),
        "aws_growth_multiple": round(rr[1] / rr[0], 2),
        "ec2_share_of_aws_usage": round(rr[2], 4),
        "ec2_first7_avg": round(rr[3], 2),
        "ec2_last7_avg": round(rr[4], 2),
    }

    # 4. Environment and the dev off-hours estimate
    env = con.execute("""
        select coalesce(environment, '(untagged)') env, sum(billed_cost) amt
        from main.fct_daily_cost where provider = 'AWS' and charge_category = 'usage'
        group by 1 order by 2 desc""").df()
    total = env.amt.sum()
    f["environment"] = {r.env: {"cost": round(r.amt, 2), "share": round(r.amt / total, 4)} for r in env.itertuples()}

    hours = con.execute("""
        select isodow(c.charge_period_start) dow, hour(c.charge_period_start) hr, sum(c.billed_cost) amt
        from main.stg_focus__charges c
        join main.int_charge_tags t using (charge_id)
        where c.provider = 'AWS' and c.charge_category = 'usage'
          and c.service_name = 'Amazon Elastic Compute Cloud' and t.environment = 'dev'
        group by 1, 2""").df()
    in_hours = hours.dow.isin(WORK_DAYS) & hours.hr.isin(list(WORK_HOURS))
    dev_ec2 = hours.amt.sum()
    off = hours.amt[~in_hours].sum()
    f["dev_schedule"] = {
        "dev_ec2_cost": round(dev_ec2, 2),
        "dev_ec2_off_hours_cost": round(off, 2),
        "off_hours_share": round(off / dev_ec2, 4),
        "window": "Mon-Fri 08:00-20:00 UTC",
    }

    # 5. Commitment coverage and the steady floor
    cm = one(con, """
        select sum(billed_cost) filter (where pricing_category = 'Standard'),
               sum(billed_cost)
        from main.fct_daily_cost
        where provider = 'AWS' and charge_category = 'usage' and service_name = 'Amazon Elastic Compute Cloud'""")
    floor = one(con, """
        select min(usage_cost), count(*) from main.mart_daily_usage
        where provider = 'AWS' and service_name = 'Amazon Elastic Compute Cloud'""")
    f["commitment"] = {
        "ec2_on_demand_cost": round(cm[0], 2),
        "ec2_cost": round(cm[1], 2),
        "ec2_on_demand_share": round(cm[0] / cm[1], 4),
        "ec2_min_daily": round(floor[0], 2),
        "ec2_floor_month": round(floor[0] * floor[1], 2),
        "ec2_floor_share": round(floor[0] * floor[1] / cm[1], 4),
    }

    # 6. Attribution gaps
    tc = con.execute("""
        select service_name, usage_cost, no_owner_cost from main.mart_tag_coverage
        where provider = 'AWS' order by no_owner_cost desc nulls last limit 3""").df()
    tg = one(con, """select sum(usage_cost), sum(no_owner_cost), sum(no_environment_cost)
                     from main.mart_tag_coverage where provider = 'AWS'""")
    raw_keys = one(con, """select count(distinct k) from (select unnest(json_keys(tags_json)) k
                           from main.stg_focus__charges where tags_json is not null)""")[0]
    f["attribution"] = {
        "aws_usage": round(tg[0], 2),
        "aws_no_owner": round(tg[1], 2),
        "aws_no_owner_share": round(tg[1] / tg[0], 4),
        "aws_no_environment": round(tg[2], 2),
        "aws_no_environment_share": round(tg[2] / tg[0], 4),
        "top_no_owner_services": [
            {"service": r.service_name, "no_owner_cost": round(r.no_owner_cost, 2)} for r in tc.itertuples()],
        "distinct_raw_tag_keys": raw_keys,
    }

    # 7. Anomaly rule comparison
    comp = pd.read_csv(OUT / "rule_comparison.csv")
    an = pd.read_csv(OUT / "anomalies.csv")
    f["anomaly"] = {
        "rule_comparison": comp.to_dict(orient="records"),
        "flags": an[["charge_date", "service_name", "actual", "expected", "upper", "direction", "excess"]]
        .to_dict(orient="records"),
        "totals": {
            "forecast": int(comp.forecast_flags.sum()),
            "static": int(comp.static_flags.sum()),
            "day_over_day": int(comp.day_over_day_flags.sum()),
            "days_scored": int(comp.days_scored.sum()),
        },
    }

    (OUT / "findings.json").write_text(json.dumps(f, indent=2, default=str))
    print(json.dumps(f, indent=2, default=str))


if __name__ == "__main__":
    main()
