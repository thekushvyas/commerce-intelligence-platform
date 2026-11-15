"""Turn recommendations into testable experiments: sample sizes, durations and guardrails."""
from __future__ import annotations

import math

import pandas as pd
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

from ..config import ANALYSIS_END, ANALYSIS_START
from ..db import query
from ._common import save_table


def n_per_arm_proportion(p0: float, rel_lift: float, alpha: float = 0.05, power: float = 0.8) -> int:
    p1 = p0 * (1 + rel_lift)
    es = proportion_effectsize(p1, p0)
    return int(math.ceil(NormalIndPower().solve_power(effect_size=abs(es), alpha=alpha, power=power, alternative="two-sided")))


def n_per_arm_mean(mean: float, sd: float, rel_lift: float, alpha: float = 0.05, power: float = 0.8) -> int:
    es = (mean * rel_lift) / sd
    return int(math.ceil(NormalIndPower().solve_power(effect_size=abs(es), alpha=alpha, power=power, alternative="two-sided")))


def run(con, results: dict | None = None) -> dict:
    base = query(
        con,
        f"""
        select count(*) / count(distinct date_trunc('week', purchase_date)) orders_per_week,
               avg(gmv) aov, stddev_samp(gmv) aov_sd,
               avg(is_detractor::int) detractor_rate,
               avg(is_late::int) filter (where is_delivered) late_rate
        from marts.fact_orders
        where purchase_date between date '2018-03-01' and date '{ANALYSIS_END}'
        """,
    ).iloc[0]
    late_detractor = query(
        con,
        f"""select avg(is_detractor::int) r from marts.fact_orders
            where is_late and purchase_date between date '2018-03-01' and date '{ANALYSIS_END}'""",
    ).r.iloc[0]
    opw = float(base.orders_per_week)
    # baseline for T1: detractor rate among the top-20% risk orders scored by the late-delivery model
    flagged_detractor = float(late_detractor)
    try:
        from ..config import TABLE_DIR
        rs = pd.read_csv(TABLE_DIR / "risk_scores.csv", parse_dates=["purchase_date"])
        rs = rs[rs.purchase_date >= "2018-03-01"]
        cut = rs.p_late.quantile(0.8)
        flagged = rs[rs.p_late >= cut][["order_id"]]
        det = query(con, "select order_id, is_detractor::int d from marts.fact_orders where is_detractor is not null")
        flagged_detractor = float(flagged.merge(det, on="order_id").d.mean())
    except Exception:
        pass

    tests = [
        {
            "test": "T1 Proactive delay notification",
            "hypothesis": "Telling customers whose order is flagged high-risk (top 2 risk deciles) that it may arrive late, with a new ETA and a small voucher, cuts 1-2 star reviews among flagged orders.",
            "unit": "order", "metric": "detractor rate among flagged orders",
            "baseline": flagged_detractor, "mde_relative": -0.25,
            "eligible_per_week": opw * 0.20,
        },
        {
            "test": "T2 Seller shipping SLA (handling <= 2 days)",
            "hypothesis": "Enforcing a 2-day handling SLA for B/C/D-tier sellers reduces late deliveries.",
            "unit": "order", "metric": "late delivery rate",
            "baseline": float(base.late_rate), "mde_relative": -0.20,
            "eligible_per_week": opw * 0.60,
        },
        {
            "test": "T3 Win-back campaign for Lapsed High-Value",
            "hypothesis": "A 10% voucher emailed to Lapsed High-Value customers lifts 60-day repurchase vs a holdout.",
            "unit": "customer", "metric": "60-day repurchase rate",
            "baseline": 0.012, "mde_relative": 0.50,
            "eligible_per_week": None,  # one-shot list of ~14k customers
        },
        {
            "test": "T4 Free-shipping threshold (R$150)",
            "hypothesis": "Free shipping above R$150 raises AOV without eroding contribution.",
            "unit": "order", "metric": "average order value",
            "baseline": float(base.aov), "mde_relative": 0.05,
            "eligible_per_week": opw,
        },
    ]
    rows = []
    for t in tests:
        if t["metric"] == "average order value":
            n = n_per_arm_mean(t["baseline"], float(base.aov_sd), t["mde_relative"])
        else:
            n = n_per_arm_proportion(t["baseline"], t["mde_relative"])
        weeks = (2 * n / t["eligible_per_week"]) if t["eligible_per_week"] else None
        rows.append({**t, "n_per_arm": n, "weeks_to_run": math.ceil(weeks) if weeks else None,
                     "feasible": (weeks is not None and weeks <= 12) or (t["eligible_per_week"] is None and 2 * n <= 14000)})
    df = pd.DataFrame(rows)
    save_table(df, "experiment_plan")
    return {
        "orders_per_week_2018": opw,
        "aov_2018": float(base.aov), "aov_sd_2018": float(base.aov_sd),
        "detractor_rate_late_2018": float(late_detractor),
        "detractor_rate_flagged_top20pct_2018": flagged_detractor,
        "tests": {r["test"]: {"n_per_arm": r["n_per_arm"], "weeks": r["weeks_to_run"], "baseline": r["baseline"], "mde_relative": r["mde_relative"], "feasible": bool(r["feasible"])} for r in rows},
    }
