"""Executive KPIs: GMV, orders, AOV, customers, sellers, growth, category and payment mix."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import ANALYSIS_END, ANALYSIS_START, PALETTE, SEQUENTIAL
from ..db import query
from ..viz import fmt_thousands, new_fig, save
from ._common import save_table

WINDOW = f"purchase_date between date '{ANALYSIS_START}' and date '{ANALYSIS_END}'"


def monthly(con) -> pd.DataFrame:
    return query(
        con,
        f"""
        select purchase_month,
               count(*)                                           as orders,
               sum(gmv)                                           as gmv,
               sum(product_revenue)                               as product_revenue,
               sum(freight_value)                                 as freight,
               count(distinct customer_unique_id)                 as customers,
               count(distinct primary_seller_id)                  as active_sellers,
               sum(gmv) / count(*)                                as aov,
               avg(is_late::int) filter (where is_delivered)      as late_rate,
               avg(review_score)                                  as avg_review,
               avg(is_repeat_order::int)                          as repeat_order_share,
               count(*) filter (where is_cancelled) / count(*)    as cancel_rate
        from marts.fact_orders
        where {WINDOW}
        group by 1 order by 1
        """,
    )


def run(con) -> dict:
    m = monthly(con)
    save_table(m, "kpi_monthly")

    tot = query(
        con,
        f"""
        select sum(gmv) gmv, count(*) orders, count(distinct customer_unique_id) customers,
               count(distinct primary_seller_id) sellers, sum(gmv)/count(*) aov,
               sum(freight_value)/sum(product_revenue) freight_share,
               avg(is_late::int) filter (where is_delivered) late_rate,
               avg(review_score) avg_review,
               avg(is_detractor::int) detractor_rate,
               count(*) filter (where is_cancelled)/count(*) cancel_rate,
               avg(n_items) items_per_order,
               avg(max_installments) avg_installments
        from marts.fact_orders where {WINDOW}
        """,
    ).iloc[0]

    yoy = query(
        con,
        """
        select year(purchase_date) yr, sum(gmv) gmv, count(*) orders, count(distinct customer_unique_id) customers
        from marts.fact_orders
        where (purchase_date between date '2017-01-01' and date '2017-07-31')
           or (purchase_date between date '2018-01-01' and date '2018-07-31')
        group by 1 order by 1
        """,
    )
    gmv_yoy = yoy.loc[yoy.yr == 2018, "gmv"].iloc[0] / yoy.loc[yoy.yr == 2017, "gmv"].iloc[0] - 1
    orders_yoy = yoy.loc[yoy.yr == 2018, "orders"].iloc[0] / yoy.loc[yoy.yr == 2017, "orders"].iloc[0] - 1

    cat = query(
        con,
        f"""
        select coalesce(category,'unknown') category, sum(item_gmv) gmv, count(*) items,
               count(distinct order_id) orders, avg(item_price) avg_price,
               avg(freight_ratio) freight_ratio, avg(review_score) avg_review,
               avg(is_late::int) filter (where is_delivered) late_rate
        from marts.fact_order_items where {WINDOW}
        group by 1 order by gmv desc
        """,
    )
    cat["gmv_share"] = cat.gmv / cat.gmv.sum()
    cat["cum_share"] = cat.gmv_share.cumsum()
    save_table(cat, "kpi_category")

    pay = query(
        con,
        f"""
        select payment_type, count(distinct order_id) orders, sum(payment_value) value,
               avg(payment_installments) avg_installments,
               avg(payment_value) avg_payment
        from marts.fact_payments where {WINDOW}
        group by 1 order by value desc
        """,
    )
    pay["value_share"] = pay.value / pay.value.sum()
    save_table(pay, "kpi_payment_type")

    inst = query(
        con,
        f"""
        select case when max_installments <= 1 then '1'
                    when max_installments between 2 and 3 then '2-3'
                    when max_installments between 4 and 6 then '4-6'
                    when max_installments between 7 and 10 then '7-10'
                    else '10+' end as installments_band,
               count(*) orders, avg(gmv) aov, sum(gmv) gmv
        from marts.fact_orders where {WINDOW} and max_installments is not null
        group by 1 order by max(max_installments)
        """,
    )
    save_table(inst, "kpi_installments")

    dow = query(
        con,
        f"""
        select d.day_name, d.day_of_week, hour(f.purchased_at) hr, count(*) orders
        from marts.fact_orders f join marts.dim_date d on d.date_day = f.purchase_date
        where {WINDOW} group by 1,2,3 order by 2,3
        """,
    )
    save_table(dow, "kpi_orders_by_dow_hour")

    # ---- figures ------------------------------------------------------------
    fig, ax = new_fig(10, 4.2)
    x = pd.to_datetime(m.purchase_month)
    ax.bar(x, m.gmv, width=22, color=PALETTE[0])
    ax.set_title("Monthly GMV (BRL), Jan-2017 to Jul-2018")
    fmt_thousands(ax, prefix="R$")
    bf = m.loc[m.purchase_month == "2017-11"]
    if len(bf):
        ax.annotate("Black Friday", (pd.to_datetime("2017-11-01"), bf.gmv.iloc[0]), xytext=(0, 6),
                    textcoords="offset points", ha="center", fontsize=9)
    save(fig, "01_monthly_gmv")

    fig, ax = new_fig(10, 4.2)
    ax.plot(x, m.customers, color=PALETTE[0], label="Ordering customers")
    ax.plot(x, m.active_sellers, color=PALETTE[1], label="Active sellers")
    ax.set_yscale("log")
    ax.set_title("Monthly active customers vs. active sellers (log scale)")
    ax.legend(loc="lower right")
    save(fig, "02_customers_vs_sellers")

    top = cat.head(12).iloc[::-1]
    fig, ax = new_fig(9, 5)
    ax.barh(top.category.str.replace("_", " "), top.gmv, color=PALETTE[0], height=0.65)
    ax.grid(axis="x")
    ax.grid(False, axis="y")
    fmt_thousands(ax, axis="x", prefix="R$")
    ax.set_title("Top 12 categories by GMV")
    for i, (g, s) in enumerate(zip(top.gmv, top.gmv_share)):
        ax.text(g, i, f"  {s:.1%}", va="center", fontsize=8, color="#52514e")
    save(fig, "03_category_gmv")

    piv = dow.pivot_table(index="day_of_week", columns="hr", values="orders", aggfunc="sum").fillna(0)
    piv.index = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][: len(piv)]
    fig, ax = new_fig(10, 3.4)
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list("seq", SEQUENTIAL)
    im = ax.imshow(piv.values, aspect="auto", cmap=cmap)
    ax.set_yticks(range(len(piv.index)), piv.index)
    ax.set_xticks(range(0, 24, 2), [f"{h:02d}h" for h in range(0, 24, 2)])
    ax.grid(False)
    ax.set_title("When do people buy? Orders by weekday and hour")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    save(fig, "04_orders_heatmap")

    peak = piv.stack().idxmax()
    return {
        "window": f"{ANALYSIS_START}..{ANALYSIS_END}",
        "gmv_total": float(tot.gmv),
        "orders": int(tot.orders),
        "customers": int(tot.customers),
        "sellers": int(tot.sellers),
        "aov": float(tot.aov),
        "freight_share_of_product_revenue": float(tot.freight_share),
        "late_rate": float(tot.late_rate),
        "avg_review": float(tot.avg_review),
        "detractor_rate": float(tot.detractor_rate),
        "cancel_rate": float(tot.cancel_rate),
        "items_per_order": float(tot.items_per_order),
        "avg_installments": float(tot.avg_installments),
        "gmv_yoy_ytd": float(gmv_yoy),
        "orders_yoy_ytd": float(orders_yoy),
        "top_category": cat.category.iloc[0],
        "top_category_share": float(cat.gmv_share.iloc[0]),
        "top10_category_share": float(cat.gmv_share.head(10).sum()),
        "credit_card_value_share": float(pay.loc[pay.payment_type == "credit_card", "value_share"].iloc[0]),
        "boleto_value_share": float(pay.loc[pay.payment_type == "boleto", "value_share"].iloc[0]),
        "peak_day_hour": f"{peak[0]} {int(peak[1]):02d}:00",
        "black_friday_month_gmv": float(bf.gmv.iloc[0]) if len(bf) else None,
        "peak_month": m.loc[m.gmv.idxmax(), "purchase_month"],
    }
