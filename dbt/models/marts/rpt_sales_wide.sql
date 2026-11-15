-- One Big Table at order-line grain for Tableau / Power BI self-service. Everything pre-joined.
select
    i.order_id, i.order_item_id, i.product_id, i.seller_id, i.customer_unique_id,
    i.purchase_date, i.purchase_month, d.year, d.quarter, d.month_name, d.week_start, d.day_name, d.is_weekend,
    i.order_status, i.is_delivered, i.is_cancelled, i.is_late, i.is_repeat_order,
    f.delivery_bucket, f.delivery_days, f.promised_days, f.days_vs_estimate,
    f.review_score, f.is_detractor, f.is_promoter,
    f.primary_payment_type, f.max_installments,
    i.category, i.item_price, i.freight_value, i.item_gmv, i.freight_ratio, i.weight_g, i.volume_litres,
    i.customer_state, cg.region as customer_region, cg.city as customer_city, cg.lat as customer_lat, cg.lng as customer_lng,
    i.seller_state, sg.region as seller_region, sg.city as seller_city, sg.lat as seller_lat, sg.lng as seller_lng,
    i.is_interstate,
    s.acquired_via_funnel, s.acquisition_origin, s.business_segment as seller_segment,
    c.cohort_month as customer_cohort_month, c.is_repeat_customer, c.n_orders as customer_lifetime_orders
from {{ ref('fact_order_items') }} i
join {{ ref('fact_orders') }} f using (order_id)
left join {{ ref('dim_date') }} d on d.date_day = i.purchase_date
left join {{ ref('dim_customer') }} c on c.customer_unique_id = i.customer_unique_id
left join {{ ref('dim_seller') }} s on s.seller_id = i.seller_id
left join {{ ref('dim_geography') }} cg on cg.zip_prefix = f.customer_zip_prefix
left join {{ ref('dim_geography') }} sg on sg.zip_prefix = s.zip_prefix
