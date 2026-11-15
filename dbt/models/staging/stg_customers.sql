select
    customer_id,
    customer_unique_id,
    lpad(customer_zip_code_prefix, 5, '0')   as zip_prefix,
    lower(trim(customer_city))               as city,
    upper(trim(customer_state))              as state
from {{ source('olist_raw', 'olist_customers_dataset') }}
