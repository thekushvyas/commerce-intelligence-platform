"""Export the warehouse for BI tools: CSV + Parquet marts, a Tableau .hyper extract, scored customer/order tables."""
from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from .config import BI_DATA_DIR, BI_DIR, ROOT, TABLE_DIR
from .db import query

MARTS = ["dim_date", "dim_customer", "dim_seller", "dim_product", "dim_geography",
         "fact_orders", "fact_order_items", "fact_payments", "fact_seller_funnel", "rpt_sales_wide"]
PARQUET_DIR = ROOT / "data" / "marts"


def scored_tables(con) -> dict[str, pd.DataFrame]:
    """Join the model outputs (RFM segment, CLV, risk score) back to the dimensions so BI users get them."""
    out = {}
    rfm = pd.read_csv(TABLE_DIR / "rfm_customers.csv")
    clv = pd.read_csv(TABLE_DIR / "clv_customers.csv")[["customer_unique_id", "p_alive", "pred_purchases_12m", "clv_12m"]]
    cust = query(con, "select customer_unique_id, state, cohort_month, first_order_date, n_orders, lifetime_gmv, is_repeat_customer from marts.dim_customer")
    cs = cust.merge(rfm[["customer_unique_id", "recency_days", "frequency", "monetary", "r_score", "f_score", "m_score", "rfm", "segment", "cluster"]],
                    on="customer_unique_id", how="left").merge(clv, on="customer_unique_id", how="left")
    out["customer_scores"] = cs
    risk = pd.read_csv(TABLE_DIR / "risk_scores.csv")[["order_id", "p_late"]]
    prop = pd.read_csv(TABLE_DIR / "propensity_scores.csv")[["customer_unique_id", "p_repeat_180d"]]
    out["order_risk_scores"] = risk
    out["customer_repeat_propensity"] = prop
    return out


def _rounded_select(con, table: str) -> str:
    """SELECT list that rounds doubles to 4 dp (keeps CSVs ~30% smaller without losing meaning)."""
    cols = con.sql(f"describe marts.{table}").df()
    parts = []
    for _, c in cols.iterrows():
        if c["column_type"].upper() in ("DOUBLE", "FLOAT"):
            parts.append(f'round("{c["column_name"]}", 4) as "{c["column_name"]}"')
        else:
            parts.append(f'"{c["column_name"]}"')
    return ", ".join(parts)


def export_csv_parquet(con) -> list[Path]:
    BI_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for t in MARTS:
        con.sql(f"copy (select * from marts.{t}) to '{PARQUET_DIR / (t + '.parquet')}' (format parquet, compression zstd)")
        written.append(PARQUET_DIR / (t + ".parquet"))
        if t != "fact_order_items":  # redundant with rpt_sales_wide for BI; keep the CSV set lean
            con.sql(f"copy (select {_rounded_select(con, t)} from marts.{t}) to '{BI_DATA_DIR / (t + '.csv')}' (header, delimiter ',')")
            written.append(BI_DATA_DIR / (t + ".csv"))
    for name, df in scored_tables(con).items():
        p = BI_DATA_DIR / f"{name}.csv"
        df.to_csv(p, index=False)
        written.append(p)
    return written


def export_hyper(con) -> Path:
    """One .hyper file with the star schema inside; opens directly in Tableau Desktop / Public."""
    from tableauhyperapi import (Connection, CreateMode, HyperProcess, SqlType, TableDefinition, TableName,
                                 Telemetry, escape_string_literal, Nullability)

    out = BI_DIR / "tableau" / "commerce_intel.hyper"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    type_map = {"BIGINT": SqlType.big_int(), "INTEGER": SqlType.int(), "DOUBLE": SqlType.double(), "FLOAT": SqlType.double(),
                "BOOLEAN": SqlType.bool(), "DATE": SqlType.date(), "TIMESTAMP": SqlType.timestamp(), "VARCHAR": SqlType.text(),
                "HUGEINT": SqlType.double(), "DECIMAL": SqlType.double()}
    tables = ["rpt_sales_wide", "fact_orders", "dim_customer", "dim_seller", "dim_product", "dim_date", "dim_geography", "fact_seller_funnel"]
    with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        with Connection(hp.endpoint, str(out), CreateMode.CREATE_AND_REPLACE) as hc:
            hc.catalog.create_schema("Extract")
            for t in tables:
                cols = con.sql(f"describe marts.{t}").df()
                tdef = TableDefinition(TableName("Extract", t))
                for _, c in cols.iterrows():
                    base = c["column_type"].split("(")[0].upper()
                    tdef.add_column(c["column_name"], type_map.get(base, SqlType.text()), Nullability.NULLABLE)
                hc.catalog.create_table(tdef)
                csv_path = BI_DATA_DIR / f"{t}.csv"
                if not csv_path.exists():
                    con.sql(f"copy (select {_rounded_select(con, t)} from marts.{t}) to '{csv_path}' (header, delimiter ',')")
                hc.execute_command(f"COPY {tdef.table_name} FROM {escape_string_literal(str(csv_path))} WITH (format csv, header, delimiter ',')")
            # scored tables too
            for name in ["customer_scores", "order_risk_scores"]:
                df = pd.read_csv(BI_DATA_DIR / f"{name}.csv")
                tdef = TableDefinition(TableName("Extract", name))
                for col, dt in df.dtypes.items():
                    st = SqlType.double() if dt.kind == "f" else SqlType.big_int() if dt.kind == "i" else SqlType.bool() if dt.kind == "b" else SqlType.text()
                    tdef.add_column(col, st, Nullability.NULLABLE)
                hc.catalog.create_table(tdef)
                hc.execute_command(f"COPY {tdef.table_name} FROM {escape_string_literal(str(BI_DATA_DIR / (name + '.csv')))} WITH (format csv, header, delimiter ',')")
    return out


def run(con) -> dict:
    files = export_csv_parquet(con)
    hyper = export_hyper(con)
    sizes = {str(p.relative_to(ROOT)): round(p.stat().st_size / 1e6, 2) for p in files + [hyper]}
    return {"files_written": len(sizes), "sizes_mb": sizes}
