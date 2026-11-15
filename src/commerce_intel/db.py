"""Thin DuckDB helpers. Every analytics module reads from the dbt-built marts through these."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from .config import DUCKDB_PATH, SQL_DIR


def connect(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    if not DUCKDB_PATH.exists():
        raise FileNotFoundError(
            f"{DUCKDB_PATH} not found. Run `make warehouse` (dbt build) first."
        )
    return duckdb.connect(str(DUCKDB_PATH), read_only=read_only)


def query(con: duckdb.DuckDBPyConnection, sql: str, **params) -> pd.DataFrame:
    """Run SQL and return a DataFrame. Named params are substituted with .format()."""
    if params:
        sql = sql.format(**params)
    return con.sql(sql).df()


def query_file(con: duckdb.DuckDBPyConnection, name: str, **params) -> pd.DataFrame:
    """Run one of the named business-question queries in sql/analysis/."""
    path = SQL_DIR / "analysis" / name
    if not path.suffix:
        path = path.with_suffix(".sql")
    return query(con, Path(path).read_text(), **params)


def table_exists(con: duckdb.DuckDBPyConnection, schema: str, table: str) -> bool:
    df = con.sql(
        f"select count(*) as n from information_schema.tables "
        f"where table_schema = '{schema}' and table_name = '{table}'"
    ).df()
    return int(df["n"].iloc[0]) > 0
