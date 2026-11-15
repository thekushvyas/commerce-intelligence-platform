select * from {{ ref('fact_orders') }} where purchase_date > date '2018-12-31' or purchase_date < date '2016-01-01'
