"""Probabilistic customer lifetime value: BG/NBD (purchase frequency) + Gamma-Gamma (spend)."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from ..config import ANALYSIS_END, ANALYSIS_START, PALETTE, SNAPSHOT_DATE
from ..db import query
from ..viz import fmt_thousands, new_fig, save
from ._common import save_table

warnings.filterwarnings("ignore")


def rfm_summary(tx: pd.DataFrame, obs_end: pd.Timestamp) -> pd.DataFrame:
    """BG/NBD inputs per customer (same definitions as lifetimes.utils.summary_data_from_transaction_data):
    frequency = repeat purchase *days*, recency = days first->last purchase, T = days first purchase->obs_end,
    monetary_value = mean spend per repeat purchase day (0 for one-time buyers)."""
    daily = tx.groupby(["customer_unique_id", "purchase_date"], as_index=False).gmv.sum()
    g = daily.groupby("customer_unique_id")
    first, last = g.purchase_date.min(), g.purchase_date.max()
    out = pd.DataFrame({
        "frequency": g.size() - 1,
        "recency": (last - first).dt.days.astype(float),
        "T": (obs_end - first).dt.days.astype(float),
    })
    rep = daily[daily.purchase_date > daily.customer_unique_id.map(first)]
    out["monetary_value"] = rep.groupby("customer_unique_id").gmv.mean().reindex(out.index).fillna(0.0)
    out.index.name = "customer_unique_id"
    return out


def calibration_holdout(tx: pd.DataFrame, cal_end: pd.Timestamp, obs_end: pd.Timestamp) -> pd.DataFrame:
    cal = rfm_summary(tx[tx.purchase_date <= cal_end], cal_end).rename(
        columns={"frequency": "frequency_cal", "recency": "recency_cal", "T": "T_cal", "monetary_value": "monetary_value_cal"})
    hold = tx[(tx.purchase_date > cal_end) & (tx.purchase_date <= obs_end)]
    hold_days = hold.groupby(["customer_unique_id", "purchase_date"]).size().groupby("customer_unique_id").size()
    cal["frequency_holdout"] = hold_days.reindex(cal.index).fillna(0).astype(float)
    cal["duration_holdout"] = float((obs_end - cal_end).days)
    return cal


def run(con) -> dict:
    from lifetimes import BetaGeoFitter, GammaGammaFitter

    tx = query(
        con,
        f"""
        select customer_unique_id, purchase_date, gmv
        from marts.fact_orders
        where purchase_date between date '{ANALYSIS_START}' and date '{ANALYSIS_END}' and not is_cancelled and gmv > 0
        """,
    )
    tx["purchase_date"] = pd.to_datetime(tx.purchase_date)
    summary = rfm_summary(tx, pd.Timestamp(SNAPSHOT_DATE))
    bgf = BetaGeoFitter(penalizer_coef=0.01)
    bgf.fit(summary.frequency, summary.recency, summary["T"])

    returning = summary[summary.frequency > 0]
    corr = float(returning[["frequency", "monetary_value"]].corr().iloc[0, 1])
    # Gamma-Gamma is only valid when q > 1 (finite mean). On a 97%-one-time-buyer base it often is not,
    # so we fit it for reference and fall back to an empirical-Bayes shrinkage of each customer's
    # average order value toward the population mean (prior weight = 2 orders).
    ggf = GammaGammaFitter(penalizer_coef=0.01)
    ggf.fit(returning.frequency, returning.monetary_value)
    gg_valid = float(ggf.params_["q"]) > 1.0
    per_cust = tx.groupby("customer_unique_id").gmv.agg(["sum", "count"])
    pop_mean = float(tx.gmv.mean())
    prior_n = 2.0
    shrunk = (per_cust["sum"] + prior_n * pop_mean) / (per_cust["count"] + prior_n)
    summary = summary.join(per_cust.rename(columns={"sum": "hist_gmv", "count": "hist_orders"}))

    horizon = 365
    summary["pred_purchases_12m"] = bgf.conditional_expected_number_of_purchases_up_to_time(
        horizon, summary.frequency, summary.recency, summary["T"])
    summary["p_alive"] = bgf.conditional_probability_alive(summary.frequency, summary.recency, summary["T"])
    if gg_valid:
        summary["exp_order_value"] = ggf.conditional_expected_average_profit(summary.frequency, summary.monetary_value)
    else:
        summary["exp_order_value"] = shrunk.reindex(summary.index)
    summary["clv_12m"] = summary.pred_purchases_12m * summary.exp_order_value
    summary["clv_12m_plus_history"] = summary.clv_12m + summary.hist_gmv
    save_table(summary.reset_index(), "clv_customers")

    # calibration: fit on first 12 months, hold out last 8
    cal = calibration_holdout(tx, pd.Timestamp("2017-12-31"), pd.Timestamp(SNAPSHOT_DATE))
    bgf_cal = BetaGeoFitter(penalizer_coef=0.01).fit(cal.frequency_cal, cal.recency_cal, cal.T_cal)
    cal["pred_holdout"] = bgf_cal.conditional_expected_number_of_purchases_up_to_time(
        cal.duration_holdout, cal.frequency_cal, cal.recency_cal, cal.T_cal)
    holdout_actual = float(cal.frequency_holdout.sum())
    holdout_pred = float(cal.pred_holdout.sum())
    grp = cal.groupby("frequency_cal").agg(actual=("frequency_holdout", "mean"), predicted=("pred_holdout", "mean"), n=("pred_holdout", "size"))
    grp = grp[grp.n >= 20]
    save_table(grp.reset_index(), "clv_calibration_by_frequency")

    # decile table
    summary["decile"] = pd.qcut(summary.clv_12m.rank(method="first"), 10, labels=range(10, 0, -1)).astype(int)
    dec = summary.groupby("decile").agg(customers=("clv_12m", "size"), avg_clv_12m=("clv_12m", "mean"),
                                        total_clv_12m=("clv_12m", "sum"), avg_p_alive=("p_alive", "mean")).sort_index()
    dec["clv_share"] = dec.total_clv_12m / dec.total_clv_12m.sum()
    save_table(dec.reset_index(), "clv_deciles")

    fig, ax = new_fig(8, 4)
    ax.bar(dec.index.astype(str), dec.clv_share, color=PALETTE[0])
    ax.xaxis.set_inverted(False)
    ax.set_title("Predicted 12-month CLV: share of value by customer decile (1 = highest)")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel("CLV decile")
    save(fig, "09_clv_deciles")

    fig, ax = new_fig(8, 4)
    ax.plot(grp.index, grp.actual, marker="o", ms=5, color=PALETTE[0], label="Actual (holdout Jan-Jul 2018)")
    ax.plot(grp.index, grp.predicted, marker="o", ms=5, color=PALETTE[1], label="BG/NBD predicted")
    ax.set_xlabel("repeat purchases in calibration period (2017)")
    ax.set_ylabel("avg purchases in holdout")
    ax.set_title("BG/NBD calibration vs. holdout")
    ax.legend()
    save(fig, "10_clv_calibration")

    return {
        "bgnbd_params": {k: float(v) for k, v in bgf.params_.items()},
        "gg_params": {k: float(v) for k, v in ggf.params_.items()},
        "gg_valid_q_gt_1": gg_valid,
        "spend_model": "gamma_gamma" if gg_valid else "empirical_bayes_shrinkage",
        "population_aov": pop_mean,
        "freq_monetary_corr": corr,
        "avg_clv_12m": float(summary.clv_12m.mean()),
        "median_clv_12m": float(summary.clv_12m.median()),
        "top_decile_clv_share": float(dec.loc[1, "clv_share"]),
        "top_decile_avg_clv": float(dec.loc[1, "avg_clv_12m"]),
        "avg_p_alive": float(summary.p_alive.mean()),
        "holdout_actual_purchases": holdout_actual,
        "holdout_predicted_purchases": holdout_pred,
        "holdout_error_pct": float(holdout_pred / holdout_actual - 1) if holdout_actual else None,
        "expected_repeat_purchases_12m_total": float(summary.pred_purchases_12m.sum()),
    }
