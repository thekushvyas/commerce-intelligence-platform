-- Grain: one row per order. The core fact for KPI, delivery, review and retention analysis.
with items as (
    select
        order_id,
        count(*)                      as n_items,
        count(distinct product_id)    as n_distinct_products,
        count(distinct seller_id)     as n_sellers,
        sum(item_price)               as product_revenue,
        sum(freight_value)            as freight_value,
        sum(item_gmv)                 as gmv,
        max(shipping_limit_at)        as shipping_limit_at
    from {{ ref('stg_order_items') }} group by 1
),
pay as (
    select
        order_id,
        sum(payment_value)                                     as payment_value,
        max(payment_installments)                              as max_installments,
        count(*)                                               as n_payments,
        arg_max(payment_type, payment_value)                   as primary_payment_type,
        bool_or(payment_type = 'voucher')                      as used_voucher
    from {{ ref('stg_order_payments') }} group by 1
),
cust as (
    select o.order_id, c.customer_unique_id, c.zip_prefix as customer_zip_prefix, c.state as customer_state,
           row_number() over (partition by c.customer_unique_id order by o.purchased_at, o.order_id) as customer_order_seq
    from {{ ref('stg_orders') }} o join {{ ref('stg_customers') }} c using (customer_id)
),
main_seller as (
    select order_id, arg_max(seller_id, item_gmv) as primary_seller_id
    from {{ ref('stg_order_items') }} group by 1
),
main_cat as (
    select i.order_id, arg_max(p.category, i.item_gmv) as primary_category
    from {{ ref('stg_order_items') }} i join {{ ref('stg_products') }} p using (product_id) group by 1
)
select
    o.order_id,
    o.customer_id,
    cu.customer_unique_id,
    cu.customer_order_seq,
    cu.customer_order_seq > 1                                     as is_repeat_order,
    cu.customer_zip_prefix,
    cu.customer_state,
    ms.primary_seller_id,
    ss.state                                                      as seller_state,
    mc.primary_category,
    o.order_status, o.is_delivered, o.is_cancelled,
    o.purchased_at, o.purchase_date,
    cast(strftime(o.purchase_date, '%Y%m%d') as integer)          as purchase_date_key,
    strftime(o.purchase_date, '%Y-%m')                            as purchase_month,
    o.approved_at, o.shipped_at, o.delivered_at, o.estimated_delivery_at,
    o.approval_days, o.handling_days, o.transit_days, o.delivery_days, o.promised_days, o.days_vs_estimate,
    o.is_late,
    case when o.delivered_at is null then null
         when o.days_vs_estimate <= -7 then 'A. >1 week early'
         when o.days_vs_estimate <  0  then 'B. Early'
         when o.days_vs_estimate =  0  then 'C. On the day'
         when o.days_vs_estimate <= 3  then 'D. 1-3 days late'
         when o.days_vs_estimate <= 7  then 'E. 4-7 days late'
         else 'F. >1 week late' end                                as delivery_bucket,
    cu.customer_state <> ss.state                                 as is_interstate,
    coalesce(i.n_items, 0)              as n_items,
    coalesce(i.n_distinct_products, 0)  as n_distinct_products,
    coalesce(i.n_sellers, 0)            as n_sellers,
    coalesce(i.product_revenue, 0)      as product_revenue,
    coalesce(i.freight_value, 0)        as freight_value,
    coalesce(i.gmv, 0)                  as gmv,
    case when i.product_revenue > 0 then i.freight_value / i.product_revenue end as freight_ratio,
    p.payment_value, p.max_installments, p.n_payments, p.primary_payment_type, p.used_voucher,
    r.review_score, r.is_detractor, r.is_promoter, r.has_comment, r.review_created_at,
    date_diff('hour', r.review_created_at, r.review_answered_at) / 24.0 as review_response_days
from {{ ref('stg_orders') }} o
left join cust cu using (order_id)
left join items i using (order_id)
left join pay p using (order_id)
left join {{ ref('stg_order_reviews') }} r using (order_id)
left join main_seller ms using (order_id)
left join {{ ref('stg_sellers') }} ss on ss.seller_id = ms.primary_seller_id
left join main_cat mc using (order_id)
