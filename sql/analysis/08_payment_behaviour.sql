-- Q8. Installments: do customers who split payments spend more? (AOV by installment band and payment type)
select primary_payment_type,
       case when max_installments <= 1 then '1' when max_installments <= 3 then '2-3'
            when max_installments <= 6 then '4-6' when max_installments <= 10 then '7-10' else '10+' end as installments,
       count(*) orders, avg(gmv) aov, sum(gmv) gmv, avg(review_score) avg_review
from marts.fact_orders
where purchase_date between date '2017-01-01' and date '2018-07-31' and max_installments is not null
group by 1, 2
order by 1, max(max_installments);
