-- Q4. How does arriving late (vs. the promised date) change the review a customer leaves?
select delivery_bucket,
       count(*)                                    as orders,
       count(*) * 1.0 / sum(count(*)) over ()      as share_of_orders,
       avg(review_score)                           as avg_review,
       avg(is_detractor::int)                      as detractor_rate,
       avg(is_promoter::int)                       as promoter_rate,
       median(delivery_days)                       as median_delivery_days
from marts.fact_orders
where is_delivered and delivered_at is not null and review_score is not null
  and purchase_date between date '2017-01-01' and date '2018-07-31'
group by 1 order by 1;
