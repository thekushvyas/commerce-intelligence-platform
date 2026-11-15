-- Q1. Monthly scorecard: GMV, orders, AOV, buyers, active sellers, MoM growth.
with m as (
    select purchase_month,
           sum(gmv)                                   as gmv,
           count(*)                                   as orders,
           count(distinct customer_unique_id)         as buyers,
           count(distinct primary_seller_id)          as active_sellers,
           sum(gmv) / count(*)                        as aov
    from marts.fact_orders
    where purchase_date between date '2017-01-01' and date '2018-07-31'
    group by 1
)
select *,
       gmv / lag(gmv) over (order by purchase_month) - 1          as gmv_mom,
       gmv / lag(gmv, 12) over (order by purchase_month) - 1      as gmv_yoy,
       sum(gmv) over (order by purchase_month)                    as cumulative_gmv
from m
order by purchase_month;
