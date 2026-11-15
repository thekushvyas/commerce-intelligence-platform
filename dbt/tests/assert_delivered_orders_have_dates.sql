-- Delivered orders are expected to carry a delivery timestamp; allow a small known number of raw-data gaps (<0.1%).
with s as (
    select count(*) filter (where is_delivered and delivered_at is null) as missing, count(*) filter (where is_delivered) as delivered
    from {{ ref('fact_orders') }}
)
select * from s where missing > 0.001 * delivered
