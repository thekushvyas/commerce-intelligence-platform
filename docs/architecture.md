# Architecture

```mermaid
flowchart LR
    subgraph Raw["Raw data (11 CSVs, 1.56M rows)"]
        A1[orders] --- A2[order_items] --- A3[payments] --- A4[reviews]
        A5[customers] --- A6[sellers] --- A7[products] --- A8[geolocation 1M]
        A9[MQLs 8K] --- A10[closed deals]
    end
    Raw -->|dbt sources, read_csv_auto| S

    subgraph DuckDB["DuckDB warehouse (dbt-duckdb)"]
        S[staging views<br/>10 models: typing, dedupe, translation] --> M[marts tables<br/>5 dims + 4 facts + 1 OBT]
        M --> T[59 dbt tests<br/>unique / not-null / relationships /<br/>GMV reconciliation / custom]
    end

    M --> P
    subgraph P["Python analytics  (src/commerce_intel)"]
        direction TB
        P1[kpis, retention, segmentation, clv]
        P2[delivery -> reviews logit]
        P3[late-delivery risk GBM<br/>point-in-time features]
        P4[sellers, funnel, geo]
        P5[forecast backtest]
        P6[experiment design]
    end

    P --> R1[reports/tables/*.csv<br/>reports/figures/*.png<br/>results.json]
    R1 --> D[reports/dashboard.html<br/>docs/index.html  GitHub Pages]
    M --> B[bi/  Tableau .hyper, Power BI M + DAX,<br/>CSV + Parquet marts, scored tables]
    R1 --> B
    R1 --> N[executed notebook]
    T -.-> CI[GitHub Actions: build -> test -> report]
```

## Layers

| Layer | Tool | What it does |
|---|---|---|
| Ingest | Python `ingest.py` | downloads the 11 CSVs from a public mirror, validates row counts against the published Kaggle dataset |
| Transform | dbt-duckdb (`dbt/`) | 10 staging views -> 10 mart tables (star schema + one-big-table), 59 tests |
| Analyse | Python package (`src/commerce_intel/analytics`) | 12 modules, each `run(con) -> dict` writing CSV tables + PNG figures |
| Query library | `sql/analysis/*.sql` | 13 named business questions in plain SQL (window functions, LOD-style CTEs) |
| Serve | `report.py` | one self-contained HTML dashboard (Plotly), also published to GitHub Pages |
| BI | `bi_export.py` + `bi/` | `.hyper` extract, Power Query + DAX, CSV/Parquet marts with model scores joined on |
| Verify | pytest + dbt tests + CI | data contracts, metric guard-rails, model sanity; `make all` is reproducible |

## Design decisions
- **DuckDB over Postgres/BigQuery**: zero infrastructure, the whole warehouse is a 150 MB file, SQL is ANSI with window functions; dbt-duckdb gives the same lineage/tests you would have in Snowflake.
- **Two grains of customer**: raw `customer_id` is per order; `customer_unique_id` is the person. All retention/CLV work uses the person.
- **Complete-month window**: the extract is right-censored after ~21 Aug 2018, so monthly metrics use Jan-2017..Jul-2018 and the weekly forecast uses weeks to 19 Aug 2018.
- **Point-in-time features**: the late-delivery model computes each seller's historical late rate using only orders delivered before the order being scored, and is evaluated on a forward-in-time split.
- **Honest model reporting**: the repeat-purchase model is kept and reported with its weak AUC because the negative result carries a business message.
