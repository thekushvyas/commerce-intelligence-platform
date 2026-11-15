-- Q2. Monthly acquisition cohorts and the share of each cohort ordering again N months later.
with first_order as (
    select customer_unique_id, min(purchase_date) as first_date
    from marts.fact_orders where not is_cancelled group by 1
),
activity as (
    select f.customer_unique_id,
           strftime(fo.first_date, '%Y-%m')                                      as cohort,
           date_diff('month', date_trunc('month', fo.first_date), date_trunc('month', f.purchase_date)) as month_n
    from marts.fact_orders f join first_order fo using (customer_unique_id)
    where not f.is_cancelled
),
sizes as (select cohort, count(distinct customer_unique_id) as cohort_size from activity where month_n = 0 group by 1)
select a.cohort, s.cohort_size, a.month_n,
       count(distinct a.customer_unique_id)                         as active_customers,
       count(distinct a.customer_unique_id) * 1.0 / s.cohort_size   as retention
from activity a join sizes s using (cohort)
where a.cohort between '2017-01' and '2018-08'
group by 1, 2, 3
order by 1, 3;
