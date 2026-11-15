-- Q11. Seller scorecard with percentile ranks on volume, reliability and satisfaction.
with s as (
    select seller_id, state, n_orders, gmv, late_rate, avg_review_score, n_reviews
    from marts.dim_seller where n_orders > 0
)
select *,
       percent_rank() over (order by gmv)                                       as volume_pct,
       percent_rank() over (order by coalesce(late_rate, 0.07) desc)            as reliability_pct,
       percent_rank() over (order by coalesce(avg_review_score, 4.0))           as satisfaction_pct,
       round(100 * (0.5 * percent_rank() over (order by gmv)
                  + 0.25 * percent_rank() over (order by coalesce(late_rate, 0.07) desc)
                  + 0.25 * percent_rank() over (order by coalesce(avg_review_score, 4.0))), 1) as health_score
from s
order by health_score desc;
