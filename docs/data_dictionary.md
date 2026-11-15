# Data dictionary (marts schema)

Built by dbt into `data/warehouse/commerce_intel.duckdb` and exported to `data/marts/*.parquet`. GMV = item price + freight (what the customer pays). All money in BRL.

## `dim_date`  (1,096 rows)

Calendar 2016-2018 (date_key = yyyymmdd).

| column | type |
|---|---|
| `date_day` | DATE |
| `date_key` | INTEGER |
| `year` | BIGINT |
| `quarter` | BIGINT |
| `month` | BIGINT |
| `year_month` | VARCHAR |
| `month_start` | TIMESTAMP |
| `week_start` | TIMESTAMP |
| `month_name` | VARCHAR |
| `day_of_week` | BIGINT |
| `day_name` | VARCHAR |
| `is_weekend` | BOOLEAN |
| `year_quarter_key` | BIGINT |

## `dim_customer`  (96,096 rows)

One row per person (customer_unique_id). Raw customer_id is per order and is collapsed here.

| column | type |
|---|---|
| `customer_unique_id` | VARCHAR |
| `zip_prefix` | VARCHAR |
| `city` | VARCHAR |
| `state` | VARCHAR |
| `first_order_at` | TIMESTAMP |
| `last_order_at` | TIMESTAMP |
| `first_order_date` | DATE |
| `cohort_month` | VARCHAR |
| `n_orders` | BIGINT |
| `n_delivered_orders` | BIGINT |
| `lifetime_gmv` | DOUBLE |
| `is_repeat_customer` | BOOLEAN |
| `customer_tenure_days` | BIGINT |

## `dim_seller`  (3,095 rows)

One row per seller with lifetime performance and, where the seller came through the marketing funnel, the deal record.

| column | type |
|---|---|
| `seller_id` | VARCHAR |
| `zip_prefix` | VARCHAR |
| `city` | VARCHAR |
| `state` | VARCHAR |
| `first_sale_at` | TIMESTAMP |
| `last_sale_at` | TIMESTAMP |
| `seller_cohort_month` | VARCHAR |
| `n_orders` | BIGINT |
| `n_items` | BIGINT |
| `gmv` | DOUBLE |
| `product_revenue` | DOUBLE |
| `late_rate` | DOUBLE |
| `avg_review_score` | DOUBLE |
| `n_reviews` | BIGINT |
| `acquired_via_funnel` | BOOLEAN |
| `won_at` | TIMESTAMP |
| `acquisition_origin` | VARCHAR |
| `business_segment` | VARCHAR |
| `lead_type` | VARCHAR |
| `lead_behaviour_profile` | VARCHAR |
| `business_type` | VARCHAR |

## `dim_product`  (32,951 rows)

One row per product with English category (two untranslated categories patched) and sales totals.

| column | type |
|---|---|
| `product_id` | VARCHAR |
| `category` | VARCHAR |
| `category_pt` | VARCHAR |
| `name_length` | INTEGER |
| `description_length` | INTEGER |
| `photos_qty` | INTEGER |
| `weight_g` | DOUBLE |
| `length_cm` | DOUBLE |
| `height_cm` | DOUBLE |
| `width_cm` | DOUBLE |
| `volume_litres` | DOUBLE |
| `n_items_sold` | BIGINT |
| `gmv` | DOUBLE |
| `avg_price` | DOUBLE |

## `dim_geography`  (15,078 rows)

One row per 5-digit zip prefix: centroid of the 1M raw geolocation pings (bounded to Brazil), state fallback for 163 prefixes.

| column | type |
|---|---|
| `zip_prefix` | VARCHAR |
| `city` | VARCHAR |
| `state` | VARCHAR |
| `lat` | DOUBLE |
| `lng` | DOUBLE |
| `has_exact_geo` | BOOLEAN |
| `region` | VARCHAR |

## `fact_orders`  (99,441 rows)

One row per order: fulfilment timestamps and lead times, lateness vs promise, basket totals, payment summary, review.

| column | type |
|---|---|
| `order_id` | VARCHAR |
| `customer_id` | VARCHAR |
| `customer_unique_id` | VARCHAR |
| `customer_order_seq` | BIGINT |
| `is_repeat_order` | BOOLEAN |
| `customer_zip_prefix` | VARCHAR |
| `customer_state` | VARCHAR |
| `primary_seller_id` | VARCHAR |
| `seller_state` | VARCHAR |
| `primary_category` | VARCHAR |
| `order_status` | VARCHAR |
| `is_delivered` | BOOLEAN |
| `is_cancelled` | BOOLEAN |
| `purchased_at` | TIMESTAMP |
| `purchase_date` | DATE |
| `purchase_date_key` | INTEGER |
| `purchase_month` | VARCHAR |
| `approved_at` | TIMESTAMP |
| `shipped_at` | TIMESTAMP |
| `delivered_at` | TIMESTAMP |
| `estimated_delivery_at` | TIMESTAMP |
| `approval_days` | DOUBLE |
| `handling_days` | DOUBLE |
| `transit_days` | DOUBLE |
| `delivery_days` | DOUBLE |
| `promised_days` | BIGINT |
| `days_vs_estimate` | BIGINT |
| `is_late` | BOOLEAN |
| `delivery_bucket` | VARCHAR |
| `is_interstate` | BOOLEAN |
| `n_items` | BIGINT |
| `n_distinct_products` | BIGINT |
| `n_sellers` | BIGINT |
| `product_revenue` | DOUBLE |
| `freight_value` | DOUBLE |
| `gmv` | DOUBLE |
| `freight_ratio` | DOUBLE |
| `payment_value` | DOUBLE |
| `max_installments` | INTEGER |
| `n_payments` | BIGINT |
| `primary_payment_type` | VARCHAR |
| `used_voucher` | BOOLEAN |
| `review_score` | INTEGER |
| `is_detractor` | BOOLEAN |
| `is_promoter` | BOOLEAN |
| `has_comment` | BOOLEAN |
| `review_created_at` | TIMESTAMP |
| `review_response_days` | DOUBLE |

## `fact_order_items`  (112,650 rows)

One row per order line with denormalised order/product/seller attributes.

| column | type |
|---|---|
| `order_id` | VARCHAR |
| `order_item_id` | INTEGER |
| `product_id` | VARCHAR |
| `seller_id` | VARCHAR |
| `customer_unique_id` | VARCHAR |
| `customer_state` | VARCHAR |
| `purchase_date` | DATE |
| `purchase_date_key` | INTEGER |
| `purchase_month` | VARCHAR |
| `order_status` | VARCHAR |
| `is_delivered` | BOOLEAN |
| `is_cancelled` | BOOLEAN |
| `is_late` | BOOLEAN |
| `is_repeat_order` | BOOLEAN |
| `delivery_days` | DOUBLE |
| `review_score` | INTEGER |
| `category` | VARCHAR |
| `seller_state` | VARCHAR |
| `is_interstate` | BOOLEAN |
| `item_price` | DOUBLE |
| `freight_value` | DOUBLE |
| `item_gmv` | DOUBLE |
| `shipping_limit_at` | TIMESTAMP |
| `weight_g` | DOUBLE |
| `volume_litres` | DOUBLE |
| `freight_ratio` | DOUBLE |

## `fact_payments`  (103,883 rows)

One row per payment record (an order can have several: card + vouchers).

| column | type |
|---|---|
| `order_id` | VARCHAR |
| `payment_sequential` | INTEGER |
| `payment_type` | VARCHAR |
| `payment_installments` | INTEGER |
| `payment_value` | DOUBLE |
| `purchase_date` | DATE |
| `purchase_month` | VARCHAR |
| `customer_state` | VARCHAR |
| `order_gmv` | DOUBLE |

## `fact_seller_funnel`  (8,000 rows)

One row per marketing-qualified lead, joined to closed deal and to the seller's realised sales.

| column | type |
|---|---|
| `mql_id` | VARCHAR |
| `first_contact_date` | DATE |
| `landing_page_id` | VARCHAR |
| `origin` | VARCHAR |
| `contact_month` | VARCHAR |
| `seller_id` | VARCHAR |
| `sdr_id` | VARCHAR |
| `sr_id` | VARCHAR |
| `won_at` | TIMESTAMP |
| `business_segment` | VARCHAR |
| `lead_type` | VARCHAR |
| `lead_behaviour_profile` | VARCHAR |
| `business_type` | VARCHAR |
| `declared_catalog_size` | DOUBLE |
| `declared_monthly_revenue` | DOUBLE |
| `is_closed` | BOOLEAN |
| `days_to_close` | BIGINT |
| `is_activated` | BOOLEAN |
| `first_sale_at` | TIMESTAMP |
| `days_won_to_first_sale` | BIGINT |
| `seller_orders` | BIGINT |
| `seller_gmv` | DOUBLE |
| `seller_avg_review` | DOUBLE |
| `seller_late_rate` | DOUBLE |

## `rpt_sales_wide`  (112,650 rows)

One Big Table at order-line grain for BI tools - everything pre-joined.

| column | type |
|---|---|
| `order_id` | VARCHAR |
| `order_item_id` | INTEGER |
| `product_id` | VARCHAR |
| `seller_id` | VARCHAR |
| `customer_unique_id` | VARCHAR |
| `purchase_date` | DATE |
| `purchase_month` | VARCHAR |
| `year` | BIGINT |
| `quarter` | BIGINT |
| `month_name` | VARCHAR |
| `week_start` | TIMESTAMP |
| `day_name` | VARCHAR |
| `is_weekend` | BOOLEAN |
| `order_status` | VARCHAR |
| `is_delivered` | BOOLEAN |
| `is_cancelled` | BOOLEAN |
| `is_late` | BOOLEAN |
| `is_repeat_order` | BOOLEAN |
| `delivery_bucket` | VARCHAR |
| `delivery_days` | DOUBLE |
| `promised_days` | BIGINT |
| `days_vs_estimate` | BIGINT |
| `review_score` | INTEGER |
| `is_detractor` | BOOLEAN |
| `is_promoter` | BOOLEAN |
| `primary_payment_type` | VARCHAR |
| `max_installments` | INTEGER |
| `category` | VARCHAR |
| `item_price` | DOUBLE |
| `freight_value` | DOUBLE |
| `item_gmv` | DOUBLE |
| `freight_ratio` | DOUBLE |
| `weight_g` | DOUBLE |
| `volume_litres` | DOUBLE |
| `customer_state` | VARCHAR |
| `customer_region` | VARCHAR |
| `customer_city` | VARCHAR |
| `customer_lat` | DOUBLE |
| `customer_lng` | DOUBLE |
| `seller_state` | VARCHAR |
| `seller_region` | VARCHAR |
| `seller_city` | VARCHAR |
| `seller_lat` | DOUBLE |
| `seller_lng` | DOUBLE |
| `is_interstate` | BOOLEAN |
| `acquired_via_funnel` | BOOLEAN |
| `acquisition_origin` | VARCHAR |
| `seller_segment` | VARCHAR |
| `customer_cohort_month` | VARCHAR |
| `is_repeat_customer` | BOOLEAN |
| `customer_lifetime_orders` | BIGINT |
