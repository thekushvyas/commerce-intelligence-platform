"""Delivery performance and its effect on customer satisfaction (review score)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from ..config import ANALYSIS_END, ANALYSIS_START, PALETTE, STATUS
from ..db import query
from ..viz import fmt_pct, new_fig, save
from ._common import save_table

WINDOW = f"purchase_date between date '{ANALYSIS_START}' and date '{ANALYSIS_END}'"


def run(con) -> dict:
    d = query(
        con,
        f"""
        select order_id, delivery_days, promised_days, days_vs_estimate, is_late, delivery_bucket,
               review_score, is_detractor, customer_state, seller_state, is_interstate, freight_ratio, gmv,
               n_items, n_sellers, primary_category, purchase_month, approval_days, handling_days, transit_days
        from marts.fact_orders
        where {WINDOW} and is_delivered and delivered_at is not null and review_score is not null
        """,
    )
    d["is_late"] = d.is_late.astype(bool)

    bucket = d.groupby("delivery_bucket").agg(orders=("order_id", "size"), avg_review=("review_score", "mean"),
                                              detractor_rate=("is_detractor", "mean")).reset_index()
    bucket["share"] = bucket.orders / bucket.orders.sum()
    save_table(bucket, "delivery_bucket_reviews")

    # Where does the time go? Stage decomposition for on-time vs late
    stages = d.groupby("is_late")[["approval_days", "handling_days", "transit_days", "delivery_days", "promised_days"]].median().reset_index()
    save_table(stages, "delivery_stage_medians")

    by_state = query(
        con,
        f"""
        select customer_state state, count(*) orders, avg(delivery_days) avg_delivery_days,
               avg(promised_days) avg_promised_days, avg(is_late::int) late_rate, avg(review_score) avg_review,
               avg(freight_ratio) freight_ratio, avg(is_interstate::int) interstate_share
        from marts.fact_orders where {WINDOW} and is_delivered and delivered_at is not null
        group by 1 order by orders desc
        """,
    )
    save_table(by_state, "delivery_by_state")

    monthly = query(
        con,
        f"""
        select purchase_month, avg(is_late::int) late_rate, avg(delivery_days) avg_delivery_days,
               avg(review_score) avg_review, count(*) orders
        from marts.fact_orders where {WINDOW} and is_delivered and delivered_at is not null
        group by 1 order by 1
        """,
    )
    save_table(monthly, "delivery_monthly")

    # ---- logistic regression: P(detractor review) -------------------------------
    m = d.dropna(subset=["days_vs_estimate", "delivery_days", "freight_ratio"]).copy()
    m["late_1_3"] = ((m.days_vs_estimate >= 1) & (m.days_vs_estimate <= 3)).astype(int)
    m["late_4_7"] = ((m.days_vs_estimate >= 4) & (m.days_vs_estimate <= 7)).astype(int)
    m["late_8p"] = (m.days_vs_estimate >= 8).astype(int)
    m["multi_seller"] = (m.n_sellers > 1).astype(int)
    m["multi_item"] = (m.n_items > 1).astype(int)
    m["log_gmv"] = np.log1p(m.gmv)
    m["is_interstate"] = m.is_interstate.fillna(False).astype(int)
    m["delivery_weeks"] = m.delivery_days / 7
    m["detractor"] = m.is_detractor.astype(int)
    logit = smf.logit("detractor ~ late_1_3 + late_4_7 + late_8p + delivery_weeks + multi_seller + multi_item + log_gmv + is_interstate + freight_ratio", data=m).fit(disp=0)
    coefs = pd.DataFrame({"coef": logit.params, "odds_ratio": np.exp(logit.params), "p_value": logit.pvalues,
                          "ci_low": np.exp(logit.conf_int()[0]), "ci_high": np.exp(logit.conf_int()[1])})
    save_table(coefs.reset_index().rename(columns={"index": "term"}), "delivery_logit_odds_ratios")

    # average marginal effect of lateness (counterfactual: set all late flags to 0)
    base = logit.predict(m)
    cf = m.copy(); cf[["late_1_3", "late_4_7", "late_8p"]] = 0
    cf_pred = logit.predict(cf)
    late_mask = m.is_late
    avoided_detractors = float((base[late_mask] - cf_pred[late_mask]).sum())
    detractor_rate_ontime = float(d.loc[~d.is_late, "is_detractor"].mean())
    detractor_rate_late = float(d.loc[d.is_late, "is_detractor"].mean())
    review_ontime = float(d.loc[~d.is_late, "review_score"].mean())
    review_late = float(d.loc[d.is_late, "review_score"].mean())
    late_share_of_detractors = float(d.loc[d.is_late, "is_detractor"].sum() / d.is_detractor.sum())

    # ---- figures ------------------------------------------------------------
    fig, ax = new_fig(9, 4)
    cols = [STATUS["good"] if "early" in b.lower() or "on the" in b.lower() else STATUS["critical"] if ">1 week late" in b else STATUS["serious"] for b in bucket.delivery_bucket]
    ax.bar(bucket.delivery_bucket.str[3:], bucket.avg_review, color=cols, width=0.65)
    for i, (v, s) in enumerate(zip(bucket.avg_review, bucket.share)):
        ax.text(i, v + 0.05, f"{v:.2f}\n({s:.1%} of orders)", ha="center", fontsize=8, color="#52514e")
    ax.set_ylim(0, 5.4)
    ax.set_title("Average review score by delivery outcome vs. promise")
    save(fig, "11_review_by_delivery_bucket")

    fig, ax = new_fig(10, 4)
    x = pd.to_datetime(monthly.purchase_month)
    ax.plot(x, monthly.late_rate, color=PALETTE[1], marker="o", ms=4)
    fmt_pct(ax)
    ax.set_title("Share of delivered orders arriving after the promised date")
    peak = monthly.loc[monthly.late_rate.idxmax()]
    ax.annotate(f"{peak.late_rate:.0%} in {peak.purchase_month}", (pd.to_datetime(peak.purchase_month), peak.late_rate),
                xytext=(10, -14), textcoords="offset points", fontsize=9)
    save(fig, "12_late_rate_monthly")

    oc = coefs.drop(index="Intercept").sort_values("odds_ratio")
    fig, ax = new_fig(8, 4.5)
    ax.errorbar(oc.odds_ratio, range(len(oc)), xerr=[oc.odds_ratio - oc.ci_low, oc.ci_high - oc.odds_ratio], fmt="o", color=PALETTE[0], ecolor="#9a9995", capsize=3)
    ax.set_yticks(range(len(oc)), oc.index)
    ax.axvline(1, color="#9a9995", lw=1, ls="--")
    ax.set_xscale("log")
    ax.grid(axis="x"); ax.grid(False, axis="y")
    ax.set_title("What drives a 1-2 star review? Odds ratios (logistic regression, 95% CI)")
    save(fig, "13_detractor_odds_ratios")

    return {
        "orders_modelled": int(len(m)),
        "late_rate": float(d.is_late.mean()),
        "avg_delivery_days": float(d.delivery_days.mean()),
        "median_delivery_days": float(d.delivery_days.median()),
        "avg_promised_days": float(d.promised_days.mean()),
        "review_on_time": review_ontime,
        "review_late": review_late,
        "detractor_rate_on_time": detractor_rate_ontime,
        "detractor_rate_late": detractor_rate_late,
        "late_share_of_all_detractors": late_share_of_detractors,
        "odds_ratio_late_1_3": float(coefs.loc["late_1_3", "odds_ratio"]),
        "odds_ratio_late_4_7": float(coefs.loc["late_4_7", "odds_ratio"]),
        "odds_ratio_late_8p": float(coefs.loc["late_8p", "odds_ratio"]),
        "odds_ratio_multi_seller": float(coefs.loc["multi_seller", "odds_ratio"]),
        "odds_ratio_per_delivery_week": float(coefs.loc["delivery_weeks", "odds_ratio"]),
        "logit_pseudo_r2": float(logit.prsquared),
        "detractors_avoidable_if_on_time": avoided_detractors,
        "worst_late_month": peak.purchase_month,
        "worst_late_month_rate": float(peak.late_rate),
        "slowest_state": by_state.sort_values("avg_delivery_days").state.iloc[-1],
        "slowest_state_days": float(by_state.avg_delivery_days.max()),
        "fastest_state": by_state.sort_values("avg_delivery_days").state.iloc[0],
        "fastest_state_days": float(by_state.avg_delivery_days.min()),
        "median_transit_days_late": float(stages.loc[stages.is_late == True, "transit_days"].iloc[0]),
        "median_transit_days_on_time": float(stages.loc[stages.is_late == False, "transit_days"].iloc[0]),
        "median_handling_days_late": float(stages.loc[stages.is_late == True, "handling_days"].iloc[0]),
        "median_handling_days_on_time": float(stages.loc[stages.is_late == False, "handling_days"].iloc[0]),
    }
