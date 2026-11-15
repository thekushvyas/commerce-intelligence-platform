-- Q9. Seller-state -> customer-state lanes: volume, delivery days, late rate, freight burden.
select seller_state, customer_state,
       count(*) orders, sum(gmv) gmv,
       avg(delivery_days) avg_delivery_days, avg(is_late::int) filter (where is_delivered) late_rate,
       avg(freight_ratio) freight_ratio, avg(review_score) avg_review
from marts.fact_orders
where purchase_date between date '2017-01-01' and date '2018-07-31' and seller_state is not null
group by 1, 2
having count(*) >= 200
order by orders desc;
