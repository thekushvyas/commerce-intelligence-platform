"""Paths, analysis window and chart palette shared by every module."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("CI_PROJECT_ROOT", Path(__file__).resolve().parents[2]))
RAW_DIR = ROOT / "data" / "raw"
WAREHOUSE_DIR = ROOT / "data" / "warehouse"
DUCKDB_PATH = WAREHOUSE_DIR / "commerce_intel.duckdb"
DBT_DIR = ROOT / "dbt"
SQL_DIR = ROOT / "sql"
REPORTS_DIR = ROOT / "reports"
FIG_DIR = REPORTS_DIR / "figures"
TABLE_DIR = REPORTS_DIR / "tables"
BI_DIR = ROOT / "bi"
BI_DATA_DIR = BI_DIR / "data"
RESULTS_JSON = REPORTS_DIR / "results.json"

# The dataset runs Sep-2016 .. Oct-2018, but the extract is right-censored: daily orders fall off
# a cliff after ~2018-08-21. Monthly analyses therefore use complete months Jan-2017 .. Jul-2018;
# the weekly forecast series runs to the last complete week (ending 2018-08-19).
ANALYSIS_START = "2017-01-01"
ANALYSIS_END = "2018-07-31"
FORECAST_END = "2018-08-19"
SNAPSHOT_DATE = "2018-08-01"  # "today" for recency / CLV calculations

RANDOM_STATE = 42

# Validated, colour-blind-safe categorical order (do not re-order; order is the CVD mechanism).
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]
DIVERGING = ["#c2410c", "#eb6834", "#f6b89b", "#d4d4d0", "#86b6ef", "#2a78d6", "#104281"]
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e6e5e1"
STATUS = {"good": "#008300", "warning": "#eda100", "serious": "#eb6834", "critical": "#e34948"}

RAW_FILES = {
    "olist_orders_dataset.csv": 99441,
    "olist_order_items_dataset.csv": 112650,
    "olist_order_payments_dataset.csv": 103886,
    "olist_order_reviews_dataset.csv": 99224,
    "olist_customers_dataset.csv": 99441,
    "olist_sellers_dataset.csv": 3095,
    "olist_products_dataset.csv": 32951,
    "olist_geolocation_dataset.csv": 1000163,
    "product_category_name_translation.csv": 71,
    "olist_marketing_qualified_leads_dataset.csv": 8000,
    "olist_closed_deals_dataset.csv": 842,
}


def ensure_dirs() -> None:
    for d in (WAREHOUSE_DIR, FIG_DIR, TABLE_DIR, BI_DATA_DIR, BI_DIR / "tableau", BI_DIR / "powerbi"):
        d.mkdir(parents=True, exist_ok=True)
