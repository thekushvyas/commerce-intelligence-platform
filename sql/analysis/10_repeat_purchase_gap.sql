-- Q10. Time between first and second order, and what the second basket looks like.
with o as (
    select customer_unique_id, customer_order_seq, purchase_date, gmv, primary_category,
           lag(purchase_date) over (partition by customer_unique_id order by customer_order_seq) as prev_date,
           lag(primary_category) over (partition by customer_unique_id order by customer_order_seq) as prev_category
    from marts.fact_orders where not is_cancelled
)
select date_diff('day', prev_date, purchase_date) as days_since_prev,
       count(*) as second_orders,
       avg(gmv) as avg_second_order_gmv,
       avg((primary_category = prev_category)::int) as same_category_share
from o
where customer_order_seq = 2
group by 1
order by 1;
