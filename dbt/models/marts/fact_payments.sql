select
    p.order_id, p.payment_sequential, p.payment_type, p.payment_installments, p.payment_value,
    f.purchase_date, f.purchase_month, f.customer_state, f.gmv as order_gmv
from {{ ref('stg_order_payments') }} p
join {{ ref('fact_orders') }} f using (order_id)
