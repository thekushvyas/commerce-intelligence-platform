select
    mql_id,
    try_cast(first_contact_date as date)          as first_contact_date,
    landing_page_id,
    coalesce(nullif(lower(trim(origin)), ''), 'unknown') as origin
from {{ source('olist_raw', 'olist_marketing_qualified_leads_dataset') }}
