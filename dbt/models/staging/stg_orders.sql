-- One row per order. Casts timestamps, derives fulfilment lead times and lateness.
with src as (
    select * from {{ source('olist_raw', 'olist_orders_dataset') }}
),
typed as (
    select
        order_id,
        customer_id,
        lower(trim(order_status))                                  as order_status,
        try_cast(order_purchase_timestamp as timestamp)            as purchased_at,
        try_cast(order_approved_at as timestamp)                   as approved_at,
        try_cast(order_delivered_carrier_date as timestamp)        as shipped_at,
        try_cast(order_delivered_customer_date as timestamp)       as delivered_at,
        try_cast(order_estimated_delivery_date as timestamp)       as estimated_delivery_at
    from src
)
select
    *,
    cast(purchased_at as date)                                                        as purchase_date,
    date_diff('hour', purchased_at, approved_at) / 24.0                               as approval_days,
    date_diff('hour', approved_at, shipped_at) / 24.0                                 as handling_days,
    date_diff('hour', shipped_at, delivered_at) / 24.0                                as transit_days,
    date_diff('hour', purchased_at, delivered_at) / 24.0                              as delivery_days,
    date_diff('day', cast(purchased_at as date), cast(estimated_delivery_at as date)) as promised_days,
    date_diff('day', cast(estimated_delivery_at as date), cast(delivered_at as date)) as days_vs_estimate,
    case when delivered_at is null then null
         when cast(delivered_at as date) > cast(estimated_delivery_at as date) then true
         else false end                                                               as is_late,
    order_status = 'delivered'                                                        as is_delivered,
    order_status in ('canceled', 'unavailable')                                       as is_cancelled
from typed
