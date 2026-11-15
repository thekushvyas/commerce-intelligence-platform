import json

import pytest

from commerce_intel.config import DUCKDB_PATH, RESULTS_JSON
from commerce_intel.db import connect

needs_warehouse = pytest.mark.skipif(not DUCKDB_PATH.exists(), reason="warehouse not built (run `make warehouse`)")
needs_results = pytest.mark.skipif(not RESULTS_JSON.exists(), reason="analyses not run (run `make analyze`)")


@pytest.fixture(scope="session")
def con():
    if not DUCKDB_PATH.exists():
        pytest.skip("warehouse not built")
    c = connect()
    yield c
    c.close()


@pytest.fixture(scope="session")
def results():
    if not RESULTS_JSON.exists():
        pytest.skip("results.json missing")
    return json.loads(RESULTS_JSON.read_text())
