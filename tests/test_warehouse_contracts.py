"""Data contracts on the dbt marts that go beyond dbt's schema tests."""
import pandas as pd

from commerce_intel.db import query


def test_grain_fact_orders_matches_raw(con):
    n = query(con, "select count(*) n, count(distinct order_id) d from marts.fact_orders").iloc[0]
    assert n.n == n.d == 99441


def test_customer_dimension_collapses_to_people(con):
    r = query(con, "select count(*) people, sum(n_orders) orders from marts.dim_customer").iloc[0]
    assert r.people == 96096 and r.orders == 99441


def test_gmv_reconciles_between_facts(con):
    r = query(con, "select abs(sum(gmv) - (select sum(item_gmv) from marts.fact_order_items)) diff from marts.fact_orders").iloc[0]
    assert r["diff"] < 0.05


def test_payments_roughly_equal_gmv(con):
    # payments include vouchers/interest; aggregate gap must stay tiny
    r = query(con, "select sum(payment_value) pay, sum(gmv) gmv from marts.fact_orders where n_items > 0").iloc[0]
    assert abs(r.pay / r.gmv - 1) < 0.01


def test_late_flag_consistent_with_dates(con):
    bad = query(con, """select count(*) n from marts.fact_orders
                        where is_late and cast(delivered_at as date) <= cast(estimated_delivery_at as date)""").iloc[0].n
    assert bad == 0


def test_every_order_line_has_geo(con):
    r = query(con, """select count(*) n from marts.fact_orders f
                      left join marts.dim_geography g on g.zip_prefix = f.customer_zip_prefix where g.zip_prefix is null""").iloc[0].n
    assert r == 0


def test_funnel_grain_and_join(con):
    r = query(con, "select count(*) n, sum(is_closed::int) closed, sum(is_activated::int) act from marts.fact_seller_funnel").iloc[0]
    assert r.n == 8000 and r.closed == 842 and 300 < r.act < 842


def test_date_dimension_covers_facts(con):
    r = query(con, """select count(*) n from marts.fact_orders f left join marts.dim_date d on d.date_key = f.purchase_date_key
                      where d.date_key is null""").iloc[0].n
    assert r == 0


def test_named_sql_queries_run(con):
    from pathlib import Path

    from commerce_intel.config import SQL_DIR
    from commerce_intel.db import query_file

    files = sorted(Path(SQL_DIR, "analysis").glob("*.sql"))
    assert len(files) >= 12
    for f in files:
        df = query_file(con, f.name)
        assert isinstance(df, pd.DataFrame) and len(df) > 0, f.name
