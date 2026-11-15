"""Seller-side economics: concentration, health scoring, and seller cohorts."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import ANALYSIS_END, ANALYSIS_START, PALETTE, STATUS
from ..db import query
from ..viz import fmt_pct, fmt_thousands, new_fig, save
from ._common import save_table


def run(con) -> dict:
    s = query(
        con,
        f"""
        select s.seller_id, s.state, s.seller_cohort_month, s.acquired_via_funnel, s.acquisition_origin,
               count(distinct i.order_id) n_orders, count(*) n_items, sum(i.item_gmv) gmv,
               avg(i.is_late::int) filter (where i.is_delivered) late_rate,
               avg(i.review_score) avg_review,
               count(distinct i.category) n_categories,
               min(i.purchase_date) first_sale, max(i.purchase_date) last_sale,
               count(distinct i.purchase_month) active_months
        from marts.dim_seller s
        join marts.fact_order_items i using (seller_id)
        where i.purchase_date between date '{ANALYSIS_START}' and date '{ANALYSIS_END}' and not i.is_cancelled
        group by 1,2,3,4,5
        """,
    )
    s = s.sort_values("gmv", ascending=False).reset_index(drop=True)
    s["gmv_share"] = s.gmv / s.gmv.sum()
    s["cum_gmv_share"] = s.gmv_share.cumsum()
    s["seller_pct"] = (s.index + 1) / len(s)
    n = len(s)
    top1 = float(s.cum_gmv_share.iloc[max(int(n * 0.01) - 1, 0)])
    top10 = float(s.cum_gmv_share.iloc[int(n * 0.10) - 1])
    top20 = float(s.cum_gmv_share.iloc[int(n * 0.20) - 1])
    _trap = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
    gini = float(2 * _trap(s.cum_gmv_share, s.seller_pct) - 1)  # sellers ranked descending -> curve above diagonal

    # Health score: 0-100 from volume, reliability and satisfaction (percentile ranks).
    s["vol_pct"] = s.gmv.rank(pct=True)
    s["rel_pct"] = (1 - s.late_rate.fillna(s.late_rate.median())).rank(pct=True)
    s["sat_pct"] = s.avg_review.fillna(s.avg_review.median()).rank(pct=True)
    s["health_score"] = (100 * (0.5 * s.vol_pct + 0.25 * s.rel_pct + 0.25 * s.sat_pct)).round(1)
    s["tier"] = pd.qcut(s.health_score.rank(method="first"), [0, 0.2, 0.6, 0.9, 1.0], labels=["D: Underperforming", "C: Developing", "B: Solid", "A: Star"])
    tiers = s.groupby("tier", observed=True).agg(sellers=("seller_id", "size"), gmv=("gmv", "sum"), avg_late=("late_rate", "mean"), avg_review=("avg_review", "mean")).reset_index()
    tiers["gmv_share"] = tiers.gmv / tiers.gmv.sum()
    save_table(s, "seller_scorecard")
    save_table(tiers, "seller_tiers")

    # Problem sellers: meaningful volume but high late rate and low reviews
    problem = s[(s.n_orders >= 50) & (s.late_rate >= 0.12) & (s.avg_review <= 3.8)]
    save_table(problem, "seller_problem_list")

    # Seller cohorts: survival (still selling N months after first sale)
    coh = query(
        con,
        f"""
        with sm as (
            select seller_id, strftime(min(purchase_date), '%Y-%m') first_m, purchase_month
            from marts.fact_order_items where not is_cancelled group by seller_id, purchase_month
        ),
        base as (select seller_id, min(first_m) cohort from sm group by 1),
        act as (select b.cohort, date_diff('month', strptime(b.cohort,'%Y-%m'), strptime(sm.purchase_month,'%Y-%m')) k, count(distinct sm.seller_id) n
                from sm join base b using (seller_id) group by 1,2)
        select a.cohort, a.k, a.n / c0.n0 as active_share
        from act a join (select cohort, n n0 from act where k = 0) c0 using (cohort)
        where a.cohort between '2017-01' and '2018-02' and a.k <= 6
        order by 1,2
        """,
    )
    surv = coh.pivot(index="cohort", columns="k", values="active_share")
    save_table(surv.round(3), "seller_cohort_activity", index=True)
    surv_curve = surv.mean(axis=0)

    # State mix
    st = s.groupby("state").agg(sellers=("seller_id", "size"), gmv=("gmv", "sum")).sort_values("gmv", ascending=False).reset_index()
    st["gmv_share"] = st.gmv / st.gmv.sum()
    save_table(st, "seller_by_state")

    # ---- figures ------------------------------------------------------------
    fig, ax = new_fig(7, 4.5)
    ax.plot(s.seller_pct, s.cum_gmv_share, color=PALETTE[0])
    ax.plot([0, 1], [0, 1], color="#9a9995", lw=1, ls="--")
    ax.fill_between(s.seller_pct, s.cum_gmv_share, s.seller_pct, color=PALETTE[0], alpha=0.08)
    fmt_pct(ax); fmt_pct(ax, "x")
    ax.set_xlabel("share of sellers (ranked by GMV)")
    ax.set_ylabel("cumulative share of GMV")
    ax.set_title(f"Seller concentration: top 10% of sellers = {top10:.0%} of GMV (Gini {gini:.2f})")
    save(fig, "16_seller_concentration")

    fig, ax = new_fig(8, 4.2)
    cols = [STATUS["critical"], STATUS["serious"], PALETTE[0], STATUS["good"]]
    ax.bar(tiers.tier.astype(str), tiers.gmv_share, color=cols[: len(tiers)], width=0.6)
    for i, (g, c) in enumerate(zip(tiers.gmv_share, tiers.sellers)):
        ax.text(i, g + 0.01, f"{g:.0%} of GMV\n{c} sellers", ha="center", fontsize=8, color="#52514e")
    fmt_pct(ax)
    ax.set_title("Seller health tiers: top 10% = A, next 30% = B, next 40% = C, bottom 20% = D")
    save(fig, "17_seller_tiers")

    fig, ax = new_fig(8, 4)
    ax.plot(surv_curve.index, surv_curve.values, marker="o", ms=5, color=PALETTE[0])
    fmt_pct(ax)
    ax.set_xlabel("months since first sale")
    ax.set_title("Seller activity curve: share of a seller cohort still selling N months later")
    save(fig, "18_seller_activity_curve")

    return {
        "active_sellers": int(n),
        "top1pct_gmv_share": top1,
        "top10pct_gmv_share": top10,
        "top20pct_gmv_share": top20,
        "gini": gini,
        "sellers_single_order": int((s.n_orders == 1).sum()),
        "sellers_single_order_share": float((s.n_orders == 1).mean()),
        "median_seller_gmv": float(s.gmv.median()),
        "tier_a_sellers": int(tiers.loc[tiers.tier.astype(str).str.startswith("A"), "sellers"].sum()),
        "tier_a_gmv_share": float(tiers.loc[tiers.tier.astype(str).str.startswith("A"), "gmv_share"].sum()),
        "problem_sellers": int(len(problem)),
        "problem_sellers_gmv": float(problem.gmv.sum()),
        "problem_sellers_orders": int(problem.n_orders.sum()),
        "seller_active_m1": float(surv_curve.get(1, np.nan)),
        "seller_active_m3": float(surv_curve.get(3, np.nan)),
        "seller_active_m6": float(surv_curve.get(6, np.nan)),
        "sp_seller_gmv_share": float(st.loc[st.state == "SP", "gmv_share"].iloc[0]),
    }
