"""Repeat-purchase propensity model: who will buy again within 6 months of their first order?

A "repeat" is a second order 1-180 days after the first (same-day second orders are split checkouts, not loyalty).
Two models are fitted (gradient boosting and regularised logistic regression); the better test AUC is the champion.

Point-in-time correct: features use only what is known at the first order + its delivery/review.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer

from ..config import PALETTE, RANDOM_STATE
from ..db import query
from ..viz import new_fig, save
from ._common import save_table

HORIZON_DAYS = 180
CUTOFF = "2018-02-01"  # first orders must have 180 days of observable follow-up before 2018-07-31


def build_dataset(con) -> pd.DataFrame:
    return query(
        con,
        f"""
        with firsts as (
            select f.*, c.n_orders as lifetime_orders
            from marts.fact_orders f join marts.dim_customer c using (customer_unique_id)
            where f.customer_order_seq = 1 and f.purchase_date between date '2017-01-01' and date '{CUTOFF}'
              and f.is_delivered
        ),
        second as (
            select customer_unique_id, min(purchase_date) as second_date
            from marts.fact_orders where customer_order_seq = 2 group by 1
        ),
        geo as (select zip_prefix, lat, lng from marts.dim_geography)
        select f.customer_unique_id,
               (s.second_date is not null and date_diff('day', f.purchase_date, s.second_date) between 1 and {HORIZON_DAYS})::int as repeat_180d,
               f.gmv, f.freight_ratio, f.n_items, f.n_distinct_products, f.n_sellers,
               coalesce(f.delivery_days, 0) delivery_days, coalesce(f.days_vs_estimate, 0) days_vs_estimate,
               coalesce(f.is_late, false)::int is_late, coalesce(f.review_score, 0) review_score,
               (f.review_score is null)::int no_review, coalesce(f.has_comment, false)::int has_comment,
               coalesce(f.max_installments, 1) installments, coalesce(f.primary_payment_type, 'unknown') payment_type,
               coalesce(f.used_voucher, false)::int used_voucher,
               coalesce(f.primary_category, 'unknown') category, f.customer_state, coalesce(f.is_interstate, false)::int is_interstate,
               dayofweek(f.purchased_at) dow, hour(f.purchased_at) hr, month(f.purchased_at) purchase_month_num,
               g.lat, g.lng
        from firsts f
        left join second s using (customer_unique_id)
        left join geo g on g.zip_prefix = f.customer_zip_prefix
        """,
    )


def run(con) -> dict:
    df = build_dataset(con)
    y = df.repeat_180d.values
    num = ["gmv", "freight_ratio", "n_items", "n_distinct_products", "n_sellers", "delivery_days", "days_vs_estimate",
           "is_late", "review_score", "no_review", "has_comment", "installments", "used_voucher", "is_interstate",
           "dow", "hr", "purchase_month_num", "lat", "lng"]
    cat = ["payment_type", "category", "customer_state"]
    X = df[num + cat]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=RANDOM_STATE)

    pre = ColumnTransformer([("num", "passthrough", num),
                             ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=200, sparse_output=False), cat)])
    gbm = make_pipeline(pre, HistGradientBoostingClassifier(max_iter=400, learning_rate=0.04, max_leaf_nodes=15,
                                                           l2_regularization=1.0, class_weight=None,
                                                           random_state=RANDOM_STATE, early_stopping=True,
                                                           validation_fraction=0.15))
    gbm.fit(X_tr, y_tr)
    p_gbm = gbm.predict_proba(X_te)[:, 1]

    pre_lr = ColumnTransformer([("num", StandardScaler(), num),
                                ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=200, sparse_output=False), cat)])
    lr = make_pipeline(pre_lr, LogisticRegression(max_iter=2000, C=0.5))
    lr.fit(X_tr, y_tr)
    p_lr = lr.predict_proba(X_te)[:, 1]

    champion_name, champion, p_champ = ("gbm", gbm, p_gbm) if roc_auc_score(y_te, p_gbm) >= roc_auc_score(y_te, p_lr) else ("logistic", lr, p_lr)
    base_rate = float(y_te.mean())
    metrics = {
        "n_train": int(len(X_tr)), "n_test": int(len(X_te)), "base_rate": base_rate,
        "gbm_auc": float(roc_auc_score(y_te, p_gbm)), "gbm_pr_auc": float(average_precision_score(y_te, p_gbm)),
        "gbm_brier": float(brier_score_loss(y_te, p_gbm)),
        "lr_auc": float(roc_auc_score(y_te, p_lr)), "lr_pr_auc": float(average_precision_score(y_te, p_lr)),
        "champion": champion_name, "champion_auc": float(roc_auc_score(y_te, p_champ)),
    }

    # decile lift
    te = pd.DataFrame({"y": y_te, "p": p_champ})
    te["decile"] = pd.qcut(te.p.rank(method="first", ascending=False), 10, labels=range(1, 11)).astype(int)
    lift = te.groupby("decile").agg(customers=("y", "size"), repeaters=("y", "sum"), rate=("y", "mean")).reset_index()
    lift["lift"] = lift.rate / base_rate
    lift["cum_capture"] = lift.repeaters.cumsum() / lift.repeaters.sum()
    save_table(lift, "propensity_decile_lift")
    metrics["top_decile_lift"] = float(lift.loc[0, "lift"])
    metrics["top2_decile_capture"] = float(lift.loc[1, "cum_capture"])
    metrics["top3_decile_capture"] = float(lift.loc[2, "cum_capture"])

    # permutation importance on raw columns (model-agnostic, computed on the test set)
    pi = permutation_importance(champion, X_te, y_te, scoring="roc_auc", n_repeats=5, random_state=RANDOM_STATE, n_jobs=1)
    imp = pd.DataFrame({"feature": num + cat, "importance": pi.importances_mean, "std": pi.importances_std}).sort_values("importance", ascending=False)
    save_table(imp, "propensity_feature_importance")

    # calibration table
    te["bin"] = pd.cut(te.p, bins=[0, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2, 1.0], include_lowest=True)
    calib = te.groupby("bin", observed=True).agg(n=("y", "size"), predicted=("p", "mean"), actual=("y", "mean")).reset_index()
    calib["bin"] = calib.bin.astype(str)
    save_table(calib, "propensity_calibration")

    # score everyone (for BI) -> who to target
    df["p_repeat_180d"] = champion.predict_proba(X)[:, 1]
    save_table(df[["customer_unique_id", "repeat_180d", "p_repeat_180d"]], "propensity_scores")

    # ---- figures ------------------------------------------------------------
    fig, ax = new_fig(8, 4)
    ax.bar(lift.decile.astype(str), lift.lift, color=PALETTE[0])
    ax.axhline(1, color="#9a9995", lw=1, ls="--")
    ax.set_xlabel("propensity decile (1 = most likely to repeat)")
    ax.set_title(f"Repeat-purchase propensity: lift by decile ({champion_name}, test AUC {metrics['champion_auc']:.2f})")
    for i, v in enumerate(lift.lift):
        ax.text(i, v + 0.05, f"{v:.1f}x", ha="center", fontsize=8, color="#52514e")
    save(fig, "14_propensity_lift")

    top = imp.head(12).iloc[::-1]
    fig, ax = new_fig(8, 4.5)
    ax.barh(top.feature, top.importance, xerr=top["std"], color=PALETTE[0], height=0.6, ecolor="#9a9995")
    ax.grid(axis="x"); ax.grid(False, axis="y")
    ax.set_title("Permutation importance (drop in test AUC when feature is shuffled)")
    save(fig, "15_propensity_importance")

    metrics["top_features"] = imp.feature.head(5).tolist()
    return metrics
