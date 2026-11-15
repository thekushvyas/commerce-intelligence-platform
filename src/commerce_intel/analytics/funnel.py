"""B2B seller-acquisition funnel: MQL -> closed deal -> activated seller -> GMV, by channel."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import PALETTE
from ..db import query
from ..viz import fmt_pct, fmt_thousands, new_fig, save
from ._common import save_table


def run(con) -> dict:
    f = query(con, "select * from marts.fact_seller_funnel")
    ch = f.groupby("origin").agg(
        mqls=("mql_id", "size"), deals=("is_closed", "sum"), activated=("is_activated", "sum"),
        gmv=("seller_gmv", "sum"), orders=("seller_orders", "sum"),
        median_days_to_close=("days_to_close", "median"),
        median_days_to_first_sale=("days_won_to_first_sale", "median"),
    ).sort_values("mqls", ascending=False)
    ch["close_rate"] = ch.deals / ch.mqls
    ch["activation_rate"] = ch.activated / ch.deals.replace(0, np.nan)
    ch["mql_to_active"] = ch.activated / ch.mqls
    ch["gmv_per_mql"] = ch.gmv / ch.mqls
    ch["gmv_per_deal"] = ch.gmv / ch.deals.replace(0, np.nan)
    ch["gmv_per_active_seller"] = ch.gmv / ch.activated.replace(0, np.nan)
    save_table(ch.reset_index(), "funnel_by_channel")

    overall = {
        "mqls": int(len(f)), "deals": int(f.is_closed.sum()), "activated": int(f.is_activated.sum()),
        "close_rate": float(f.is_closed.mean()), "activation_rate": float(f.is_activated.sum() / f.is_closed.sum()),
        "mql_to_active": float(f.is_activated.mean()),
        "gmv_from_funnel_sellers": float(f.seller_gmv.sum()),
        "median_days_to_close": float(f.days_to_close.median()),
        "median_days_won_to_first_sale": float(f.days_won_to_first_sale.median()),
    }

    seg = f[f.is_closed].groupby("business_segment").agg(deals=("mql_id", "size"), activated=("is_activated", "sum"), gmv=("seller_gmv", "sum")).sort_values("gmv", ascending=False)
    seg["activation_rate"] = seg.activated / seg.deals
    seg["gmv_per_deal"] = seg.gmv / seg.deals
    save_table(seg.reset_index(), "funnel_by_segment")

    lt = f[f.is_closed].groupby("lead_type").agg(deals=("mql_id", "size"), activated=("is_activated", "sum"), gmv=("seller_gmv", "sum")).sort_values("deals", ascending=False)
    lt["activation_rate"] = lt.activated / lt.deals
    lt["gmv_per_deal"] = lt.gmv / lt.deals
    save_table(lt.reset_index(), "funnel_by_lead_type")

    prof = f[f.is_closed].groupby("lead_behaviour_profile").agg(deals=("mql_id", "size"), activated=("is_activated", "sum"), gmv=("seller_gmv", "sum"))
    prof["activation_rate"] = prof.activated / prof.deals
    prof["gmv_per_deal"] = prof.gmv / prof.deals
    save_table(prof.reset_index(), "funnel_by_behaviour_profile")

    sr = f[f.is_closed].groupby("sr_id").agg(deals=("mql_id", "size"), activated=("is_activated", "sum"), gmv=("seller_gmv", "sum"), median_days_to_close=("days_to_close", "median")).sort_values("deals", ascending=False)
    sr["activation_rate"] = sr.activated / sr.deals
    sr["gmv_per_deal"] = sr.gmv / sr.deals
    save_table(sr.reset_index(), "funnel_by_sales_rep")

    monthly = f.groupby("contact_month").agg(mqls=("mql_id", "size"), deals=("is_closed", "sum")).reset_index()
    monthly["close_rate"] = monthly.deals / monthly.mqls
    save_table(monthly, "funnel_monthly")

    # GMV concentration among activated sellers (a few deals carry the channel)
    act = f[f.is_activated].sort_values("seller_gmv", ascending=False)
    top5_share = float(act.seller_gmv.head(5).sum() / act.seller_gmv.sum())

    # declared revenue vs realised: do big promises deliver?
    decl = f[f.is_closed & (f.declared_monthly_revenue > 0)]
    decl_corr = float(np.log1p(decl.declared_monthly_revenue).corr(np.log1p(decl.seller_gmv), method="spearman")) if len(decl) > 10 else None
    if decl_corr is not None and np.isnan(decl_corr):
        decl_corr = None

    # ---- figures ------------------------------------------------------------
    c = ch[(ch.mqls >= 100) & (ch.index != "unknown")].sort_values("gmv_per_mql", ascending=True)
    fig, ax = new_fig(9, 4.5)
    ax.barh(c.index, c.gmv_per_mql, color=PALETTE[0], height=0.6)
    for i, (v, m, a) in enumerate(zip(c.gmv_per_mql, c.mqls, c.mql_to_active)):
        ax.text(v, i, f"  R${v:,.0f}  ({m:,} MQLs, {a:.1%} become active sellers)", va="center", fontsize=8, color="#52514e")
    ax.grid(axis="x"); ax.grid(False, axis="y")
    ax.set_xlim(0, c.gmv_per_mql.max() * 1.9)
    ax.set_title("GMV generated per marketing-qualified lead, by acquisition channel (unknown source excluded)")
    save(fig, "19_funnel_gmv_per_mql")

    stages = ["MQLs", "Closed deals", "Activated sellers"]
    vals = [overall["mqls"], overall["deals"], overall["activated"]]
    fig, ax = new_fig(7, 3.8)
    ax.bar(stages, vals, color=[PALETTE[0], PALETTE[0], PALETTE[0]], width=0.55)
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:,}" + (f"\n({v / vals[i - 1]:.1%} of prior)" if i else ""), ha="center", va="bottom", fontsize=9, color="#52514e")
    ax.set_ylim(0, vals[0] * 1.18)
    ax.set_title("Seller acquisition funnel (Jun-2017 to Jun-2018 leads)")
    save(fig, "20_funnel_stages")

    known = ch[(ch.mqls >= 100) & (ch.index != "unknown")]
    best = known.gmv_per_mql.idxmax()
    worst = known.gmv_per_mql.idxmin()
    return {
        **overall,
        "best_channel_gmv_per_mql": best, "best_channel_value": float(ch.loc[best, "gmv_per_mql"]),
        "worst_channel_gmv_per_mql": worst, "worst_channel_value": float(ch.loc[worst, "gmv_per_mql"]),
        "paid_search_gmv_per_mql": float(ch.loc["paid_search", "gmv_per_mql"]) if "paid_search" in ch.index else None,
        "organic_gmv_per_mql": float(ch.loc["organic_search", "gmv_per_mql"]) if "organic_search" in ch.index else None,
        "social_gmv_per_mql": float(ch.loc["social", "gmv_per_mql"]) if "social" in ch.index else None,
        "social_close_rate": float(ch.loc["social", "close_rate"]) if "social" in ch.index else None,
        "top5_activated_sellers_gmv_share": top5_share,
        "n_declared_revenue_deals": int(len(decl)),
        "unknown_origin_share": float((f.origin == "unknown").mean()),
        "declared_vs_realised_log_corr": decl_corr,
        "best_segment_gmv": seg.index[0], "best_segment_gmv_value": float(seg.gmv.iloc[0]),
        "top_rep_deals": int(sr.deals.iloc[0]),
        "n_sales_reps": int(len(sr)),
    }
