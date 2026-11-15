"""Geography: where demand, supply and friction (freight, delivery time) sit across Brazil."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import ANALYSIS_END, ANALYSIS_START, PALETTE, SEQUENTIAL
from ..db import query
from ..viz import fmt_thousands, new_fig, save
from ._common import save_table


def run(con) -> dict:
    st = query(
        con,
        f"""
        select f.customer_state state, g.region,
               count(*) orders, count(distinct f.customer_unique_id) customers, sum(f.gmv) gmv, sum(f.gmv)/count(*) aov,
               avg(f.freight_ratio) freight_ratio, avg(f.delivery_days) avg_delivery_days, avg(f.promised_days) avg_promised_days,
               avg(f.is_late::int) filter (where f.is_delivered) late_rate, avg(f.review_score) avg_review,
               avg(f.is_interstate::int) interstate_share
        from marts.fact_orders f
        left join (select state, mode(region) region from marts.dim_geography group by 1) g on g.state = f.customer_state
        where f.purchase_date between date '{ANALYSIS_START}' and date '{ANALYSIS_END}'
        group by 1,2 order by gmv desc
        """,
    )
    st["gmv_share"] = st.gmv / st.gmv.sum()
    save_table(st, "geo_state")

    reg = st.groupby("region").agg(orders=("orders", "sum"), gmv=("gmv", "sum"), avg_delivery_days=("avg_delivery_days", "mean"),
                                   late_rate=("late_rate", "mean"), freight_ratio=("freight_ratio", "mean"), avg_review=("avg_review", "mean")).sort_values("gmv", ascending=False)
    reg["gmv_share"] = reg.gmv / reg.gmv.sum()
    save_table(reg.reset_index(), "geo_region")

    flow = query(
        con,
        f"""
        select seller_state, customer_state, count(*) orders, sum(gmv) gmv, avg(delivery_days) avg_delivery_days, avg(is_late::int) late_rate
        from marts.fact_orders where purchase_date between date '{ANALYSIS_START}' and date '{ANALYSIS_END}' and seller_state is not null
        group by 1,2 order by orders desc
        """,
    )
    save_table(flow, "geo_seller_customer_flow")
    sp_to_sp = float(flow[(flow.seller_state == "SP") & (flow.customer_state == "SP")].orders.sum() / flow.orders.sum())
    from_sp = float(flow[flow.seller_state == "SP"].orders.sum() / flow.orders.sum())

    # points for dashboard scatter map (zip-prefix grain)
    pts = query(
        con,
        f"""
        select g.zip_prefix, g.lat, g.lng, g.state, g.city, count(*) orders, sum(f.gmv) gmv, avg(f.delivery_days) avg_delivery_days
        from marts.fact_orders f join marts.dim_geography g on g.zip_prefix = f.customer_zip_prefix
        where f.purchase_date between date '{ANALYSIS_START}' and date '{ANALYSIS_END}' and g.has_exact_geo
        group by 1,2,3,4,5
        """,
    )
    save_table(pts, "geo_points")

    # ---- figures ------------------------------------------------------------
    fig, ax = new_fig(7, 7)
    sz = np.sqrt(pts.gmv) / 6
    sc = ax.scatter(pts.lng, pts.lat, s=sz, c=pts.avg_delivery_days.clip(upper=30), cmap="Blues", alpha=0.55, linewidths=0)
    ax.set_aspect("equal"); ax.grid(False)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("Customer demand (bubble = GMV) coloured by average delivery days")
    fig.colorbar(sc, ax=ax, fraction=0.03, pad=0.02, label="avg delivery days (capped 30)")
    save(fig, "26_geo_bubble_map")

    top = st.head(15)
    fig, ax = new_fig(9, 4.2)
    ax.bar(top.state, top.gmv_share, color=PALETTE[0])
    ax2 = None  # single axis by design
    for i, (s_, d_) in enumerate(zip(top.gmv_share, top.avg_delivery_days)):
        ax.text(i, s_ + 0.004, f"{d_:.0f}d", ha="center", fontsize=8, color="#52514e")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_title("GMV share by customer state (label = avg delivery days)")
    save(fig, "27_geo_state_gmv")

    sp = st[st.state == "SP"].iloc[0]
    north = reg.loc["North"] if "North" in reg.index else None
    return {
        "sp_gmv_share": float(sp.gmv_share), "sp_delivery_days": float(sp.avg_delivery_days), "sp_freight_ratio": float(sp.freight_ratio),
        "top3_states_gmv_share": float(st.gmv_share.head(3).sum()),
        "southeast_gmv_share": float(reg.loc["Southeast", "gmv_share"]) if "Southeast" in reg.index else None,
        "north_gmv_share": float(north.gmv_share) if north is not None else None,
        "north_delivery_days": float(north.avg_delivery_days) if north is not None else None,
        "north_freight_ratio": float(north.freight_ratio) if north is not None else None,
        "northeast_late_rate": float(reg.loc["Northeast", "late_rate"]) if "Northeast" in reg.index else None,
        "orders_sp_to_sp_share": sp_to_sp, "orders_from_sp_sellers_share": from_sp,
        "interstate_order_share": float(query(con, f"select avg(is_interstate::int) s from marts.fact_orders where purchase_date between date '{ANALYSIS_START}' and date '{ANALYSIS_END}'").s.iloc[0]),
    }
