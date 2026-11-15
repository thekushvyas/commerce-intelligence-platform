-- fact_orders.gmv must equal the sum of its order lines (reconciliation to the cent).
with lines as (select order_id, sum(item_gmv) as line_gmv from {{ ref('fact_order_items') }} group by 1)
select f.order_id, f.gmv, l.line_gmv
from {{ ref('fact_orders') }} f join lines l using (order_id)
where abs(f.gmv - l.line_gmv) > 0.01
