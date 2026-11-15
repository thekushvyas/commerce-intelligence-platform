-- Q5. Seller concentration: cumulative GMV share by seller rank (Pareto / Lorenz input).
with s as (
    select seller_id, sum(item_gmv) as gmv
    from marts.fact_order_items
    where purchase_date between date '2017-01-01' and date '2018-07-31' and not is_cancelled
    group by 1
),
ranked as (
    select seller_id, gmv,
           row_number() over (order by gmv desc)                       as rnk,
           count(*) over ()                                            as n_sellers,
           sum(gmv) over (order by gmv desc rows unbounded preceding)  as cum_gmv,
           sum(gmv) over ()                                            as total_gmv
    from s
)
select rnk, seller_id, gmv,
       rnk * 1.0 / n_sellers   as seller_pct,
       cum_gmv / total_gmv     as cum_gmv_share
from ranked
order by rnk;
