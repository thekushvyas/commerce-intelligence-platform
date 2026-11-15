# Power BI model guide

## Load
1. Clone the repo. Parquet marts are committed under `data/marts/` (no Python needed). For the scored
   tables (`customer_scores.csv`, `order_risk_scores.csv`) run `make bi` once, or skip them.
2. In Power BI Desktop: **Get data > Parquet** for each file in `data/marts/`, or paste the queries in
   `PowerQuery.m` (set the `DataFolder` parameter first).
3. Paste the measures from `measures.dax`.

## Relationships (star schema, all many-to-one, single direction)
| From (many) | To (one) | Key |
|---|---|---|
| FactOrders[purchase_date] | DimDate[date_day] | date |
| FactOrders[customer_unique_id] | DimCustomer[customer_unique_id] | text |
| FactOrders[primary_seller_id] | DimSeller[seller_id] | text |
| FactOrders[customer_zip_prefix] | DimGeography[zip_prefix] | text |
| FactOrderItems[order_id] | FactOrders[order_id] | text |
| FactOrderItems[product_id] | DimProduct[product_id] | text |
| FactOrderItems[seller_id] | DimSeller[seller_id] | text (inactive if you keep the FactOrders->DimSeller path active; use USERELATIONSHIP) |
| FactSellerFunnel[seller_id] | DimSeller[seller_id] | text |
| CustomerScores[customer_unique_id] | DimCustomer[customer_unique_id] | 1:1 |
| OrderRiskScores[order_id] | FactOrders[order_id] | 1:1 |

Mark `DimDate` as the date table (`date_day`). `rpt_sales_wide` is a denormalised alternative if you
prefer a single flat table (Tableau-style); do not load it alongside the star to avoid double counting.

## Suggested report pages (mirrors reports/dashboard.html)
1. **Executive** - cards: GMV, Orders, Customers, AOV, Late Rate, Avg Review, GMV YoY %; line: GMV by month; bar: top categories.
2. **Customers** - matrix: cohort_month x months-since-first (use `DimCustomer[cohort_month]` and a `months_since_first` calculated column on FactOrders); bar: RFM segment customers vs GMV; decile chart from CustomerScores.
3. **Delivery & CX** - bar: Avg Review by `delivery_bucket`; line: Late Rate by month; map: Avg Delivery Days by customer_state.
4. **Sellers** - Pareto (Seller GMV Rank vs running GMV share); table: health tier, late rate, review; slicer on `acquisition_origin`.
5. **Seller acquisition** - funnel visual: MQLs > Closed Deals > Activated Sellers; bar: GMV per MQL by `origin`.
6. **Risk** - histogram of `p_late`; table of high-risk open orders by seller.

Colour: use the same palette as the Python layer - series 1 `#2a78d6`, series 2 `#eb6834`, good `#008300`, critical `#e34948`.
