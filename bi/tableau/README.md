# Tableau guide

## Open the extract
`make bi` writes **`bi/tableau/commerce_intel.hyper`** (~55 MB), a native Tableau extract containing the
whole star schema. In Tableau Desktop or Tableau Public: **Connect > More... > Tableau extract (.hyper)**.
If you cannot run Python, open `data/marts/*.parquet` (Tableau 2024.2+ reads Parquet) or ask the repo
owner for the Releases download of the .hyper file.

Tables inside the extract (schema `Extract`):

| Table | Grain | Use |
|---|---|---|
| `rpt_sales_wide` | order line | one-table source for most sheets (pre-joined customer/seller/product/date/geo) |
| `fact_orders` | order | delivery, reviews, payments, repeat flags |
| `dim_customer` | person | cohorts, lifetime metrics |
| `dim_seller` | seller | performance + acquisition channel |
| `dim_product`, `dim_date`, `dim_geography` | dimensions | |
| `fact_seller_funnel` | marketing lead | B2B funnel |
| `customer_scores` | person | RFM segment, K-means cluster, CLV, P(alive) |
| `order_risk_scores` | order | model P(late) |

Relationship model (if you prefer the star over the wide table): `fact_orders` -> `dim_customer` on
`customer_unique_id`; -> `dim_seller` on `primary_seller_id = seller_id`; -> `dim_date` on
`purchase_date = date_day`; -> `dim_geography` on `customer_zip_prefix = zip_prefix`;
`customer_scores` 1:1 to `dim_customer`; `order_risk_scores` 1:1 to `fact_orders`.

## Calculated fields worth creating
```
GMV                  SUM([item_gmv])                                    // on rpt_sales_wide
Orders               COUNTD([order_id])
AOV                  [GMV] / [Orders]
Late Rate            SUM(IF [is_delivered] AND [is_late] THEN 1 END) / SUM(IF [is_delivered] THEN 1 END)
Avg Review           AVG([review_score])
Repeat Order Share   SUM(IF [is_repeat_order] THEN 1 ELSE 0 END) / COUNT([order_id])
Customer Cohort      DATETRUNC('month', { FIXED [customer_unique_id] : MIN([purchase_date]) })      // LOD
Months Since First   DATEDIFF('month', [Customer Cohort], DATETRUNC('month', [purchase_date]))
Cohort Size          { FIXED [Customer Cohort] : COUNTD([customer_unique_id]) }
Retention            COUNTD([customer_unique_id]) / ATTR([Cohort Size])
Seller GMV Rank      RANK_UNIQUE(SUM([item_gmv]), 'desc')                                          // table calc
Cum GMV Share        RUNNING_SUM(SUM([item_gmv])) / TOTAL(SUM([item_gmv]))
GMV YoY %            (ZN(SUM([item_gmv])) - LOOKUP(ZN(SUM([item_gmv])), -12)) / ABS(LOOKUP(ZN(SUM([item_gmv])), -12))
Delivery Bucket      [delivery_bucket]  (already in the data: early / on the day / 1-3 / 4-7 / >7 days late)
```

## Dashboard layout (what the HTML dashboard shows, rebuilt natively)
1. **Executive** - KPI tiles (GMV, Orders, Customers, AOV, Late Rate, Avg Review), monthly GMV bars, top categories.
2. **Customers** - cohort retention heatmap (Customer Cohort rows x Months Since First cols, colour = Retention),
   RFM segment bars from `customer_scores.segment`, CLV decile bars.
3. **Delivery & CX** - Avg Review by Delivery Bucket (colour good/critical), Late Rate by month, filled map of
   Avg Delivery Days by `customer_state`.
4. **Sellers** - Pareto curve (Seller GMV Rank vs Cum GMV Share), health-tier bars, seller activity curve.
5. **Seller acquisition** - funnel (MQL > deal > activated) and GMV per MQL by `acquisition_origin`.
6. **Geography** - symbol map on `customer_lat`/`customer_lng` sized by GMV, coloured by delivery days.

Colours: series blue `#2a78d6`, orange `#eb6834`, good `#008300`, critical `#e34948`; sequential blue ramp
`#cde2fb -> #0d366b`. Keep one axis per chart (no dual axes), thin bars, direct labels on the few bars that matter.

Publish to Tableau Public from Desktop/Public app (**Server > Tableau Public > Save to Tableau Public**) and
paste the link into the README.
