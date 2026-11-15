"""Cohort retention, repeat purchase and inter-purchase timing."""
from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from ..config import ANALYSIS_END, ANALYSIS_START, PALETTE, SEQUENTIAL
from ..db import query
from ..viz import fmt_pct, new_fig, save
from ._common import save_table


def run(con) -> dict:
    orders = query(
        con,
        f"""
        select customer_unique_id, order_id, purchase_date, customer_order_seq, gmv
        from marts.fact_orders
        where purchase_date between date '{ANALYSIS_START}' and date '{ANALYSIS_END}'
          and not is_cancelled
        """,
    )
    orders["purchase_date"] = pd.to_datetime(orders.purchase_date)
    first = orders.groupby("customer_unique_id").purchase_date.min().rename("first_date")
    orders = orders.join(first, on="customer_unique_id")
    orders["cohort"] = orders.first_date.dt.to_period("M")
    orders["period"] = (orders.purchase_date.dt.to_period("M") - orders.cohort).apply(lambda x: x.n)

    cohort_sizes = orders[orders.period == 0].groupby("cohort").customer_unique_id.nunique()
    active = orders.groupby(["cohort", "period"]).customer_unique_id.nunique().unstack(fill_value=0)
    retention = active.div(cohort_sizes, axis=0)
    # only keep (cohort, period) cells that are fully observable
    last_period = pd.Period(ANALYSIS_END, "M")
    for c in retention.index:
        maxp = (last_period - c).n
        retention.loc[c, [p for p in retention.columns if p > maxp]] = np.nan
    retention.index = retention.index.astype(str)
    save_table(retention.round(4), "retention_matrix", index=True)

    curve = retention.iloc[:, 1:].mean(axis=0, skipna=True)
    curve_df = curve.rename("retention").reset_index().rename(columns={"index": "months_since_first"})
    save_table(curve_df, "retention_curve")

    cust = orders.groupby("customer_unique_id").agg(n_orders=("order_id", "nunique"), gmv=("gmv", "sum"))
    repeat_rate = (cust.n_orders > 1).mean()
    repeat_gmv_share = query(
        con,
        f"""
        select sum(gmv) filter (where is_repeat_order) / sum(gmv) share
        from marts.fact_orders where purchase_date between date '{ANALYSIS_START}' and date '{ANALYSIS_END}'
        """,
    ).share.iloc[0]

    # time between 1st and 2nd order
    o12 = orders[orders.customer_order_seq <= 2].pivot_table(
        index="customer_unique_id", columns="customer_order_seq", values="purchase_date", aggfunc="min"
    )
    gap = (o12[2] - o12[1]).dt.days.dropna()
    gap = gap[gap >= 0]
    gap_stats = {
        "median_days_to_2nd_order": float(gap.median()),
        "p75_days_to_2nd_order": float(gap.quantile(0.75)),
        "share_2nd_order_within_30d": float((gap <= 30).mean()),
        "share_2nd_order_same_day": float((gap == 0).mean()),
    }

    # repeat rate by first-order category and state
    by_cat = query(
        con,
        f"""
        with firsts as (
            select customer_unique_id, primary_category, customer_state
            from marts.fact_orders where customer_order_seq = 1
        ),
        c as (select customer_unique_id, n_orders from marts.dim_customer)
        select f.primary_category category, count(*) customers, avg((c.n_orders > 1)::int) repeat_rate
        from firsts f join c using (customer_unique_id)
        group by 1 having count(*) >= 500 order by 3 desc
        """,
    )
    save_table(by_cat, "retention_repeat_by_first_category")
    by_state = query(
        con,
        """
        select state, count(*) customers, avg(is_repeat_customer::int) repeat_rate
        from marts.dim_customer group by 1 having count(*) >= 300 order by 3 desc
        """,
    )
    save_table(by_state, "retention_repeat_by_state")

    # ---- figures ------------------------------------------------------------
    show = retention.iloc[:, :13].copy()
    fig, ax = new_fig(10, 6)
    cmap = LinearSegmentedColormap.from_list("seq", SEQUENTIAL)
    vals = show.iloc[:, 1:].values * 100
    im = ax.imshow(vals, aspect="auto", cmap=cmap, vmin=0, vmax=np.nanmax(vals))
    ax.set_yticks(range(len(show.index)), show.index)
    ax.set_xticks(range(vals.shape[1]), [f"M{p}" for p in show.columns[1:]])
    ax.grid(False)
    ax.set_title("Monthly cohort retention (% of cohort ordering again), months 1-12")
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            v = vals[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=6.5,
                        color="white" if v > np.nanmax(vals) * 0.55 else "#0b0b0b")
    fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02, label="% retained")
    save(fig, "05_cohort_retention")

    fig, ax = new_fig(9, 4)
    ax.hist(gap.clip(upper=365), bins=52, color=PALETTE[0])
    ax.set_title("Days between 1st and 2nd order (repeat buyers, capped at 365)")
    ax.set_xlabel("days")
    ax.axvline(gap.median(), color=PALETTE[1], lw=1.5, ls="--")
    ax.text(gap.median() + 5, ax.get_ylim()[1] * 0.9, f"median {gap.median():.0f}d", color=PALETTE[1], fontsize=9)
    save(fig, "06_days_to_second_order")

    return {
        "repeat_customer_rate": float(repeat_rate),
        "repeat_order_gmv_share": float(repeat_gmv_share),
        "month1_retention_avg": float(curve.get(1, np.nan)),
        "month3_retention_avg": float(curve.get(3, np.nan)),
        "month6_retention_avg": float(curve.get(6, np.nan)),
        "month12_retention_avg": float(curve.get(12, np.nan)),
        "best_repeat_category": by_cat.category.iloc[0],
        "best_repeat_category_rate": float(by_cat.repeat_rate.iloc[0]),
        "worst_repeat_category": by_cat.category.iloc[-1],
        "worst_repeat_category_rate": float(by_cat.repeat_rate.iloc[-1]),
        **gap_stats,
    }
