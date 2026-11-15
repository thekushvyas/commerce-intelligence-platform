with items as (
    select i.seller_id, i.order_id, i.item_gmv, i.item_price, i.freight_value, o.purchased_at, o.is_late, o.is_delivered
    from {{ ref('stg_order_items') }} i
    join {{ ref('stg_orders') }} o using (order_id)
),
rev as (
    select i.seller_id, r.review_score
    from (select distinct seller_id, order_id from {{ ref('stg_order_items') }}) i
    join {{ ref('stg_order_reviews') }} r using (order_id)
),
seller_perf as (
    select
        seller_id,
        min(purchased_at)                                   as first_sale_at,
        max(purchased_at)                                   as last_sale_at,
        count(distinct order_id)                            as n_orders,
        count(*)                                            as n_items,
        sum(item_gmv)                                       as gmv,
        sum(item_price)                                     as product_revenue,
        avg(is_late::int) filter (where is_delivered)       as late_rate
    from items group by 1
),
seller_rev as (
    select seller_id, avg(review_score) as avg_review_score, count(*) as n_reviews from rev group by 1
),
deal as (
    select seller_id, mql_id, won_at, business_segment, lead_type, lead_behaviour_profile, business_type
    from {{ ref('stg_closed_deals') }}
    qualify row_number() over (partition by seller_id order by won_at) = 1
),
mql as (
    select mql_id, origin from {{ ref('stg_marketing_qualified_leads') }}
)
select
    s.seller_id, s.zip_prefix, s.city, s.state,
    p.first_sale_at, p.last_sale_at,
    strftime(p.first_sale_at, '%Y-%m')                         as seller_cohort_month,
    coalesce(p.n_orders, 0)                                    as n_orders,
    coalesce(p.n_items, 0)                                     as n_items,
    coalesce(p.gmv, 0)                                         as gmv,
    coalesce(p.product_revenue, 0)                             as product_revenue,
    p.late_rate,
    r.avg_review_score,
    coalesce(r.n_reviews, 0)                                   as n_reviews,
    d.mql_id is not null                                       as acquired_via_funnel,
    d.won_at,
    m.origin                                                   as acquisition_origin,
    d.business_segment, d.lead_type, d.lead_behaviour_profile, d.business_type
from {{ ref('stg_sellers') }} s
left join seller_perf p using (seller_id)
left join seller_rev r using (seller_id)
left join deal d using (seller_id)
left join mql m using (mql_id)
