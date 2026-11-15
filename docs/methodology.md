# Methodology notes

## Window and definitions
- **Window**: 2017-01-01 to 2018-07-31 (complete months). Weekly forecast: weeks to 2018-08-19. Snapshot date for recency/CLV: 2018-08-01.
- **GMV** = item price + freight = what the customer paid for the goods and shipping (excludes payment interest, includes vouchers' face value).
- **Late** = delivered date (day) > estimated delivery date (day). Only delivered orders with a delivery timestamp count toward late rate.
- **Detractor** = review score 1 or 2. **Promoter** = 4 or 5. The last answered review per order is kept (raw file has duplicates).
- **Repeat customer** = `customer_unique_id` with 2+ orders in the window (any status except cancelled/unavailable).
- **True second order** (propensity label) = second order 1-180 days after the first; same-day second orders (32% of all "second orders") are split checkouts.

## Retention / cohorts
Cohort = month of first order. Retention(k) = share of the cohort with an order k months later. Cells whose k-th month falls after the window end are masked, so curves average only fully-observed cells.

## RFM and clustering
R = quintile of recency (lower recency = higher score); F from order count (1->1, 2->2, 3->4, 4+->5, because 97% have one order); M = quintile of monetary. Segment rules are tuned to a one-purchase-dominated base (Champions = recent repeaters; Lapsed High-Value = top-40% spend, lapsed). K-means on standardised (recency, log F, log M), k chosen by silhouette over 3-7 on a 15K sample.

## CLV
BG/NBD (lifetimes) on frequency/recency/T in days, penalizer 0.01. Calibration: fit on 2017, predict Jan-Jul 2018 repeat purchases, compare totals and by calibration-frequency bucket. Gamma-Gamma was fitted but its shape parameter q < 1 (undefined mean) on this base, so expected order value uses empirical-Bayes shrinkage of each customer's mean order value toward the population mean with a prior weight of 2 orders. 12-month CLV = expected purchases x expected order value (no margin/discounting applied; multiply by a contribution margin to get profit CLV).

## Delivery -> reviews
Logistic regression of detractor on lateness buckets (1-3, 4-7, 8+ days late), delivery weeks, multi-seller, multi-item, log GMV, interstate and freight ratio. Odds ratios with 95% CI. "Avoidable detractors" = sum over late orders of P(detractor | observed) - P(detractor | lateness flags set to 0): a model-based counterfactual, not a causal estimate.

## Late-delivery risk model
HistGradientBoosting vs L2 logistic regression. Features known at checkout: promised days, basket value/weight/volume, freight, items, sellers, haversine distance seller->customer (zip centroids), customer/seller state and region, category, payment type, calendar, and the seller's prior order count / late rate / mean delivery days computed only from orders delivered before the current purchase. Train < 2018-03-01, test >= 2018-03-01. Metrics: AUC, PR-AUC, Brier, decile lift, calibration table, permutation importance on the test set.

## Repeat-purchase propensity
Same model family, label = true second order within 180 days, first orders Jan-2017..Jan-2018 so every row has 180 days of follow-up. Stratified 75/25 split. Reported as weak (AUC ~0.56) on purpose.

## Forecast
Weekly GMV, 84 weeks. Rolling-origin backtest: 6 origins 4 weeks apart, 8-week horizon. Models: last-4-week mean (naive), Holt damped trend, SARIMAX(1,1,1) with drift on log GMV. Metric: WAPE and signed bias per fold, averaged.

## Seller health score
0-100 = 50% percentile rank of GMV + 25% percentile rank of on-time rate + 25% percentile rank of average review (missing late/review filled with medians). Tiers by score quantile: A top 10%, B next 30%, C next 40%, D bottom 20%. Problem list: >=50 orders, late rate >=12%, avg review <=3.8.

## Funnel
Lead grain. Close = appears in closed deals; activated = seller_id has >=1 order line. GMV per MQL = realised GMV of activated sellers / all leads from that origin, which credits channels for seller quality, not just volume.

## Experiment sizing
Two-sided alpha 0.05, power 0.80, normal approximation (statsmodels). Durations use the Mar-Jul 2018 run rate of orders per week and the eligible share for each test.

## Known data caveats
- 8 delivered orders lack a delivery timestamp; 775 orders (cancelled/unavailable) have no items; 768 have no review; 610 products have no category; 249 orders' payments differ from GMV by > R$1 (interest/vouchers).
- Marketing funnel leads span Jun-2017..Jun-2018; seller sales are observed only to Aug-2018, so late-closing deals have less time to activate.
- Review timestamps can precede delivery (reviews are solicited on the estimated date), which is why lateness is measured against the promise, not the review date.
