-- Grain: one row per marketing-qualified lead (MQL). Closed deals and post-signup sales are joined on.
-- Lets us answer: which acquisition channels produce sellers who actually generate GMV?
with mql as (select * from {{ ref('stg_marketing_qualified_leads') }}),
deal as (
    select * from {{ ref('stg_closed_deals') }}
    qualify row_number() over (partition by mql_id order by won_at) = 1
),
seller as (
    select seller_id, first_sale_at, n_orders, gmv, avg_review_score, late_rate from {{ ref('dim_seller') }}
)
select
    m.mql_id, m.first_contact_date, m.landing_page_id, m.origin,
    strftime(m.first_contact_date, '%Y-%m')                                  as contact_month,
    d.seller_id, d.sdr_id, d.sr_id, d.won_at,
    d.business_segment, d.lead_type, d.lead_behaviour_profile, d.business_type,
    d.declared_catalog_size, d.declared_monthly_revenue,
    d.mql_id is not null                                                     as is_closed,
    date_diff('day', m.first_contact_date, cast(d.won_at as date))           as days_to_close,
    s.seller_id is not null                                                  as is_activated,
    s.first_sale_at,
    date_diff('day', cast(d.won_at as date), cast(s.first_sale_at as date))  as days_won_to_first_sale,
    coalesce(s.n_orders, 0)                                                  as seller_orders,
    coalesce(s.gmv, 0)                                                       as seller_gmv,
    s.avg_review_score                                                       as seller_avg_review,
    s.late_rate                                                              as seller_late_rate
from mql m
left join deal d using (mql_id)
left join seller s using (seller_id)
