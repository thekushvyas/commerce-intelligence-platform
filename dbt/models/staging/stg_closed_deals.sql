select
    mql_id,
    seller_id,
    sdr_id,
    sr_id,
    try_cast(won_date as timestamp)                         as won_at,
    coalesce(nullif(business_segment, ''), 'unknown')       as business_segment,
    coalesce(nullif(lead_type, ''), 'unknown')              as lead_type,
    coalesce(nullif(lead_behaviour_profile, ''), 'unknown') as lead_behaviour_profile,
    coalesce(nullif(business_type, ''), 'unknown')          as business_type,
    try_cast(declared_product_catalog_size as double)       as declared_catalog_size,
    try_cast(declared_monthly_revenue as double)            as declared_monthly_revenue
from {{ source('olist_raw', 'olist_closed_deals_dataset') }}
