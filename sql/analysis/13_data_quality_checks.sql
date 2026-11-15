-- Q13. Data-quality audit of the raw files (the issues the pipeline handles).
select 'orders missing delivery date while status=delivered' as check_name,
       count(*) filter (where is_delivered and delivered_at is null) as n from marts.fact_orders
union all
select 'orders with no items (cancelled/unavailable)', count(*) from marts.fact_orders where n_items = 0
union all
select 'orders with no payment record', count(*) from marts.fact_orders where payment_value is null
union all
select 'orders with no review', count(*) from marts.fact_orders where review_score is null
union all
select 'products with no category', count(*) from marts.dim_product where category = 'unknown'
union all
select 'zip prefixes without exact coordinates', count(*) from marts.dim_geography where not has_exact_geo
union all
select 'payment total differs from GMV by > R$1', count(*) from marts.fact_orders where abs(payment_value - gmv) > 1 and n_items > 0;
