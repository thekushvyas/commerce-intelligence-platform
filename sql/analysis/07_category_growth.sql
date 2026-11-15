-- Q7. Category growth, Jan-Aug 2018 vs Jan-Aug 2017, with share shift.
with c as (
    select category, year(purchase_date) yr, sum(item_gmv) gmv
    from marts.fact_order_items
    where (purchase_date between date '2017-01-01' and date '2017-07-31')
       or (purchase_date between date '2018-01-01' and date '2018-07-31')
    group by 1, 2
)
select category,
       sum(gmv) filter (where yr = 2017) as gmv_2017,
       sum(gmv) filter (where yr = 2018) as gmv_2018,
       sum(gmv) filter (where yr = 2018) / nullif(sum(gmv) filter (where yr = 2017), 0) - 1 as yoy_growth,
       sum(gmv) filter (where yr = 2018) / sum(sum(gmv) filter (where yr = 2018)) over ()
         - sum(gmv) filter (where yr = 2017) / sum(sum(gmv) filter (where yr = 2017)) over () as share_shift_pp
from c
group by 1
having sum(gmv) filter (where yr = 2017) > 20000
order by gmv_2018 desc;
