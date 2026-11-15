"""Download (from the GitHub mirror) and validate the 11 raw CSVs."""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

from .config import RAW_DIR, RAW_FILES

MIRRORS = {
    "default": "https://raw.githubusercontent.com/Abhiram88/brazilian-ecommerce/main/dataset/",
    "funnel": "https://raw.githubusercontent.com/MarthaMueni/Marketing-Funnel-Olist/main/",
}
FUNNEL_FILES = {"olist_marketing_qualified_leads_dataset.csv", "olist_closed_deals_dataset.csv"}


def download(force: bool = False) -> list[Path]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for name in RAW_FILES:
        dest = RAW_DIR / name
        if dest.exists() and not force:
            out.append(dest)
            continue
        url = (MIRRORS["funnel"] if name in FUNNEL_FILES else MIRRORS["default"]) + name
        print(f"downloading {name} ...", file=sys.stderr)
        urllib.request.urlretrieve(url, dest)
        out.append(dest)
    return out


def validate() -> dict:
    """Row counts must match the published Kaggle dataset exactly."""
    import duckdb

    con = duckdb.connect()
    report = {}
    for name, expected in RAW_FILES.items():
        p = RAW_DIR / name
        if not p.exists():
            raise FileNotFoundError(f"missing raw file {p}; run `make data`")
        n = int(con.sql(f"select count(*) n from read_csv_auto('{p}', header=true, all_varchar=true)").df().n.iloc[0])
        md5 = hashlib.md5(p.read_bytes()).hexdigest()
        ok = n == expected
        report[name] = {"rows": n, "expected": expected, "ok": ok, "md5": md5}
        if not ok:
            raise ValueError(f"{name}: expected {expected} rows, found {n}")
    return report
