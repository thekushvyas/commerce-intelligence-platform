-- Q3. RFM scoring in pure SQL (quintiles via NTILE), snapshot date 2018-08-01.
with base as (
    select customer_unique_id,
           date_diff('day', max(purchase_date), date '2018-08-01') as recency_days,
           count(*)                                                as frequency,
           sum(gmv)                                                as monetary
    from marts.fact_orders
    where purchase_date between date '2017-01-01' and date '2018-07-31' and not is_cancelled
    group by 1
)
select *,
       ntile(5) over (order by recency_days desc)  as r_score,
       case when frequency >= 4 then 5 when frequency = 3 then 4 when frequency = 2 then 2 else 1 end as f_score,
       ntile(5) over (order by monetary)           as m_score
from base;
