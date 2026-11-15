from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..config import TABLE_DIR


def save_table(df: pd.DataFrame, name: str, index: bool = False) -> Path:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    path = TABLE_DIR / f"{name}.csv"
    df.to_csv(path, index=index)
    return path


def jsonable(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if hasattr(v, "item"):
            v = v.item()
        if isinstance(v, float):
            v = round(v, 6)
        if isinstance(v, dict):
            v = jsonable(v)
        out[k] = v
    return out


def dump_json(d: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(d), indent=2, default=str))
