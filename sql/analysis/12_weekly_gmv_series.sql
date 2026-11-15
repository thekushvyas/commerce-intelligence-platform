-- Q12. Weekly GMV series with 4-week moving average (forecasting input).
with w as (
    select date_trunc('week', purchase_date) as week_start, sum(gmv) gmv, count(*) orders
    from marts.fact_orders
    where purchase_date between date '2017-01-01' and date '2018-07-31' and not is_cancelled
    group by 1
)
select week_start, gmv, orders,
       avg(gmv) over (order by week_start rows between 3 preceding and current row) as gmv_ma4,
       gmv / lag(gmv, 52) over (order by week_start) - 1                             as gmv_yoy
from w order by 1;
