-- Grain: one row per order line. Degenerate dimensions denormalised for BI tools.
select
    i.order_id, i.order_item_id, i.product_id, i.seller_id,
    f.customer_unique_id, f.customer_state, f.purchase_date, f.purchase_date_key, f.purchase_month,
    f.order_status, f.is_delivered, f.is_cancelled, f.is_late, f.is_repeat_order, f.delivery_days, f.review_score,
    p.category,
    s.state                               as seller_state,
    f.customer_state <> s.state           as is_interstate,
    i.item_price, i.freight_value, i.item_gmv,
    i.shipping_limit_at,
    p.weight_g, p.volume_litres,
    case when i.item_price > 0 then i.freight_value / i.item_price end as freight_ratio
from {{ ref('stg_order_items') }} i
join {{ ref('fact_orders') }} f using (order_id)
left join {{ ref('stg_products') }} p using (product_id)
left join {{ ref('stg_sellers') }} s using (seller_id)
