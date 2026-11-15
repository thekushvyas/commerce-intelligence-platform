"""Command line entry point:  python -m commerce_intel <step> | all

Steps run in this order:  data -> warehouse -> analyze -> bi -> report
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from . import bi_export, ingest, report
from .config import DBT_DIR, RESULTS_JSON, ensure_dirs
from .db import connect

STEPS = ["data", "warehouse", "analyze", "bi", "report"]


def step_data() -> None:
    ingest.download()
    rep = ingest.validate()
    print(f"raw data OK: {sum(r['rows'] for r in rep.values()):,} rows across {len(rep)} files")


def step_warehouse() -> None:
    env = {**os.environ, "DBT_PROFILES_DIR": str(DBT_DIR)}
    for cmd in (["dbt", "build", "--no-use-colors"],):
        r = subprocess.run(cmd, cwd=DBT_DIR, env=env, text=True, capture_output=True)
        tail = "\n".join(r.stdout.splitlines()[-6:])
        print(tail)
        if r.returncode != 0:
            print(r.stdout[-4000:], r.stderr[-2000:], file=sys.stderr)
            raise SystemExit("dbt build failed")


def step_analyze() -> dict:
    from .analytics import clv, delivery, experiment, forecast, funnel, geo, kpis, propensity, retention, risk_model, segmentation, sellers
    from .analytics._common import dump_json

    con = connect()
    results = {}
    modules = [("kpis", kpis), ("retention", retention), ("segmentation", segmentation), ("clv", clv), ("delivery", delivery),
               ("sellers", sellers), ("funnel", funnel), ("geo", geo), ("forecast", forecast), ("risk_model", risk_model),
               ("propensity", propensity), ("experiment", experiment)]
    for name, mod in modules:
        t = time.time()
        results[name] = mod.run(con)
        print(f"  {name:<14} {time.time() - t:5.1f}s")
    dump_json(results, RESULTS_JSON)
    print(f"results -> {RESULTS_JSON}")
    return results


def step_bi() -> None:
    con = connect()
    r = bi_export.run(con)
    print(f"BI exports: {r['files_written']} files")


def step_report() -> None:
    out = report.build()
    print(f"dashboard -> {out}")


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    ensure_dirs()
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    todo = STEPS if argv[0] == "all" else argv
    for s in todo:
        if s not in STEPS:
            raise SystemExit(f"unknown step {s!r}; choose from {STEPS} or 'all'")
        print(f"==> {s}")
        globals()[f"step_{s}"]()


if __name__ == "__main__":
    main()
