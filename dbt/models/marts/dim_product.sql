with sales as (
    select product_id, count(*) as n_items_sold, sum(item_gmv) as gmv, avg(item_price) as avg_price
    from {{ ref('stg_order_items') }} group by 1
)
select
    p.*,
    coalesce(s.n_items_sold, 0) as n_items_sold,
    coalesce(s.gmv, 0)          as gmv,
    s.avg_price
from {{ ref('stg_products') }} p
left join sales s using (product_id)
