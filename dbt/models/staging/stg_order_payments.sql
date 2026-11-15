select
    order_id,
    cast(payment_sequential as integer)    as payment_sequential,
    lower(trim(payment_type))              as payment_type,
    cast(payment_installments as integer)  as payment_installments,
    cast(payment_value as double)          as payment_value
from {{ source('olist_raw', 'olist_order_payments_dataset') }}
where lower(trim(payment_type)) <> 'not_defined'
