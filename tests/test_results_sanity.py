"""Guard-rails on headline numbers so a silent pipeline change cannot ship nonsense."""
import math


def test_kpis_in_plausible_ranges(results):
    k = results["kpis"]
    assert 14e6 < k["gmv_total"] < 16e6
    assert 90_000 < k["orders"] < 100_000
    assert 140 < k["aov"] < 180
    assert 0.05 < k["late_rate"] < 0.09
    assert 3.9 < k["avg_review"] < 4.3


def test_retention_is_low_but_defined(results):
    r = results["retention"]
    assert 0.02 < r["repeat_customer_rate"] < 0.05
    assert 0 < r["month1_retention_avg"] < 0.02
    assert r["median_days_to_2nd_order"] > 0


def test_delivery_effect_direction(results):
    d = results["delivery"]
    assert d["review_on_time"] > d["review_late"] + 1.5
    assert d["odds_ratio_late_8p"] > d["odds_ratio_late_4_7"] > d["odds_ratio_late_1_3"] > 1


def test_models_beat_chance_and_are_calibrated(results):
    m = results["risk_model"]
    assert m["gbm_auc"] > 0.68
    assert m["top_decile_lift"] > 2
    assert m["gbm_brier"] < m["test_late_rate"] * (1 - m["test_late_rate"]) + 0.002  # no worse than predicting the base rate
    p = results["propensity"]
    assert p["champion_auc"] > 0.5


def test_forecast_backtest_recorded(results):
    f = results["forecast"]
    assert f["folds"] >= 4 and all(0 < v < 0.6 for v in f["backtest_wape"].values())
    assert f["best_model"] == min(f["backtest_wape"], key=f["backtest_wape"].get)


def test_segments_partition_customers(results):
    s = results["segmentation"]
    total = sum(v["customers"] for v in s["segments"].values())
    assert total == s["n_customers_scored"]
    assert math.isclose(sum(v["gmv_share"] for v in s["segments"].values()), 1.0, abs_tol=1e-6)


def test_funnel_arithmetic(results):
    f = results["funnel"]
    assert math.isclose(f["close_rate"], f["deals"] / f["mqls"], rel_tol=1e-6)
    assert f["activated"] <= f["deals"] <= f["mqls"]
