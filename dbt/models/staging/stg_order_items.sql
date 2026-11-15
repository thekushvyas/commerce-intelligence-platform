-- One row per order line (order_id + order_item_id).
select
    order_id,
    cast(order_item_id as integer)                 as order_item_id,
    product_id,
    seller_id,
    try_cast(shipping_limit_date as timestamp)     as shipping_limit_at,
    cast(price as double)                          as item_price,
    cast(freight_value as double)                  as freight_value,
    cast(price as double) + cast(freight_value as double) as item_gmv
from {{ source('olist_raw', 'olist_order_items_dataset') }}
