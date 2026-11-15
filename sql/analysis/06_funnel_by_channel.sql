-- Q6. Seller acquisition funnel by marketing channel, through to realised marketplace GMV.
select origin,
       count(*)                                           as mqls,
       sum(is_closed::int)                                as closed_deals,
       sum(is_activated::int)                             as activated_sellers,
       sum(is_closed::int) * 1.0 / count(*)               as close_rate,
       sum(is_activated::int) * 1.0 / nullif(sum(is_closed::int), 0) as activation_rate,
       sum(seller_gmv)                                    as gmv,
       sum(seller_gmv) / count(*)                         as gmv_per_mql,
       median(days_to_close)                              as median_days_to_close,
       median(days_won_to_first_sale)                     as median_days_to_first_sale
from marts.fact_seller_funnel
group by 1
order by gmv_per_mql desc;
