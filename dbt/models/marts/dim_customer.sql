-- Grain: one row per real person (customer_unique_id). customer_id in the raw data is per-order.
with orders as (
    select o.*, c.customer_unique_id, c.zip_prefix, c.city, c.state
    from {{ ref('stg_orders') }} o
    join {{ ref('stg_customers') }} c using (customer_id)
),
order_value as (
    select order_id, sum(item_gmv) as order_gmv from {{ ref('stg_order_items') }} group by 1
),
agg as (
    select
        customer_unique_id,
        arg_min(zip_prefix, purchased_at)             as zip_prefix,
        arg_min(city, purchased_at)                   as city,
        arg_min(state, purchased_at)                  as state,
        min(purchased_at)                             as first_order_at,
        max(purchased_at)                             as last_order_at,
        count(*)                                      as n_orders,
        count(*) filter (where is_delivered)          as n_delivered_orders,
        coalesce(sum(v.order_gmv), 0)                 as lifetime_gmv
    from orders o
    left join order_value v using (order_id)
    group by 1
)
select
    customer_unique_id,
    zip_prefix, city, state,
    first_order_at, last_order_at,
    cast(first_order_at as date)                              as first_order_date,
    strftime(first_order_at, '%Y-%m')                         as cohort_month,
    n_orders, n_delivered_orders, lifetime_gmv,
    n_orders > 1                                              as is_repeat_customer,
    date_diff('day', cast(first_order_at as date), cast(last_order_at as date)) as customer_tenure_days
from agg
