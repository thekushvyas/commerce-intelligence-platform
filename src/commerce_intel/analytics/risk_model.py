"""Late-delivery risk model: at checkout, which orders will miss their promised date?

All features are known at purchase time. The seller's historical late rate is computed point-in-time
(only from orders delivered before the current purchase) to avoid leakage. Train on 2017 -> Feb 2018,
test on Mar -> Jul 2018 (a true forward-in-time split).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, precision_recall_curve, roc_auc_score, roc_curve
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ..config import ANALYSIS_END, ANALYSIS_START, PALETTE, RANDOM_STATE
from ..db import query
from ..viz import fmt_pct, new_fig, save
from ._common import save_table

SPLIT_DATE = "2018-03-01"


def build_dataset(con) -> pd.DataFrame:
    return query(
        con,
        f"""
        with o as (
            select f.order_id, f.purchased_at, f.purchase_date, f.is_late::int as is_late, f.delivered_at,
                   f.promised_days, f.gmv, f.freight_value, f.product_revenue, f.freight_ratio, f.n_items, f.n_sellers,
                   f.primary_seller_id seller_id, f.customer_state, f.seller_state, f.is_interstate::int is_interstate,
                   f.primary_category category, f.max_installments, f.primary_payment_type payment_type,
                   month(f.purchased_at) purchase_month_num, dayofweek(f.purchased_at) dow, hour(f.purchased_at) hr,
                   cg.lat c_lat, cg.lng c_lng, sg.lat s_lat, sg.lng s_lng, cg.region customer_region
            from marts.fact_orders f
            left join marts.dim_geography cg on cg.zip_prefix = f.customer_zip_prefix
            left join marts.dim_seller s on s.seller_id = f.primary_seller_id
            left join marts.dim_geography sg on sg.zip_prefix = s.zip_prefix
            where f.is_delivered and f.delivered_at is not null
              and f.purchase_date between date '{ANALYSIS_START}' and date '{ANALYSIS_END}'
        ),
        items as (
            select order_id, sum(weight_g) total_weight_g, sum(volume_litres) total_volume_l, max(weight_g) max_weight_g
            from marts.fact_order_items group by 1
        ),
        -- point-in-time seller history: orders by the same seller delivered strictly before this purchase
        hist as (
            select a.order_id,
                   count(b.order_id)                        seller_prior_orders,
                   avg(b.is_late)                           seller_prior_late_rate,
                   avg(date_diff('hour', b.purchased_at, b.delivered_at) / 24.0) seller_prior_avg_days
            from o a
            left join o b on b.seller_id = a.seller_id and b.delivered_at < a.purchased_at
            group by 1
        )
        select o.*, i.total_weight_g, i.total_volume_l, i.max_weight_g,
               h.seller_prior_orders, h.seller_prior_late_rate, h.seller_prior_avg_days,
               2 * 6371 * asin(sqrt(pow(sin(radians(o.c_lat - o.s_lat) / 2), 2)
                    + cos(radians(o.s_lat)) * cos(radians(o.c_lat)) * pow(sin(radians(o.c_lng - o.s_lng) / 2), 2))) as distance_km
        from o
        left join items i using (order_id)
        left join hist h using (order_id)
        """,
    )


def run(con) -> dict:
    df = build_dataset(con)
    df["seller_prior_late_rate"] = df.seller_prior_late_rate.fillna(df.is_late.mean())
    df["seller_prior_avg_days"] = df.seller_prior_avg_days.fillna(df.seller_prior_avg_days.median())
    df["seller_prior_orders"] = df.seller_prior_orders.fillna(0)
    df["distance_km"] = df.distance_km.fillna(df.distance_km.median())
    for c in ["total_weight_g", "total_volume_l", "max_weight_g", "freight_ratio", "max_installments"]:
        df[c] = df[c].fillna(df[c].median())
    df["log_distance"] = np.log1p(df.distance_km)
    df["log_weight"] = np.log1p(df.total_weight_g)
    df["log_gmv"] = np.log1p(df.gmv)
    df["purchase_date"] = pd.to_datetime(df.purchase_date)

    num = ["promised_days", "log_gmv", "freight_ratio", "freight_value", "n_items", "n_sellers", "is_interstate",
           "max_installments", "purchase_month_num", "dow", "hr", "log_weight", "total_volume_l", "log_distance",
           "seller_prior_orders", "seller_prior_late_rate", "seller_prior_avg_days", "c_lat", "c_lng"]
    cat = ["customer_state", "seller_state", "category", "payment_type", "customer_region"]
    for c in cat:
        df[c] = df[c].fillna("unknown")

    train = df[df.purchase_date < SPLIT_DATE]
    test = df[df.purchase_date >= SPLIT_DATE]
    X_tr, y_tr = train[num + cat], train.is_late.values
    X_te, y_te = test[num + cat], test.is_late.values

    pre = ColumnTransformer([("num", "passthrough", num), ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=100, sparse_output=False), cat)])
    gbm = make_pipeline(pre, HistGradientBoostingClassifier(max_iter=600, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0,
                                                           random_state=RANDOM_STATE, early_stopping=True, validation_fraction=0.15))
    gbm.fit(X_tr, y_tr)
    p = gbm.predict_proba(X_te)[:, 1]

    pre_lr = ColumnTransformer([("num", StandardScaler(), num), ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=100, sparse_output=False), cat)])
    lr = make_pipeline(pre_lr, LogisticRegression(max_iter=3000, C=0.5)).fit(X_tr, y_tr)
    p_lr = lr.predict_proba(X_te)[:, 1]

    base = float(y_te.mean())
    m = {
        "n_train": int(len(train)), "n_test": int(len(test)), "train_late_rate": float(y_tr.mean()), "test_late_rate": base,
        "gbm_auc": float(roc_auc_score(y_te, p)), "gbm_pr_auc": float(average_precision_score(y_te, p)), "gbm_brier": float(brier_score_loss(y_te, p)),
        "lr_auc": float(roc_auc_score(y_te, p_lr)), "lr_pr_auc": float(average_precision_score(y_te, p_lr)),
        "split_date": SPLIT_DATE,
    }

    te = pd.DataFrame({"y": y_te, "p": p})
    te["decile"] = pd.qcut(te.p.rank(method="first", ascending=False), 10, labels=range(1, 11)).astype(int)
    lift = te.groupby("decile").agg(orders=("y", "size"), late=("y", "sum"), late_rate=("y", "mean")).reset_index()
    lift["lift"] = lift.late_rate / base
    lift["cum_capture"] = lift.late.cumsum() / lift.late.sum()
    save_table(lift, "risk_decile_lift")
    m["top_decile_late_rate"] = float(lift.loc[0, "late_rate"])
    m["top_decile_lift"] = float(lift.loc[0, "lift"])
    m["top_decile_capture"] = float(lift.loc[0, "cum_capture"])
    m["top2_decile_capture"] = float(lift.loc[1, "cum_capture"])

    # operating point: flag orders with p >= threshold such that precision ~ 0.3
    prec, rec, thr = precision_recall_curve(y_te, p)
    ok = np.where(prec[:-1] >= 0.30)[0]
    if len(ok):
        i = ok[0]
        m["threshold_p30"] = float(thr[i]); m["recall_at_p30"] = float(rec[i]); m["flag_rate_at_p30"] = float((p >= thr[i]).mean())

    pi = permutation_importance(gbm, X_te, y_te, scoring="roc_auc", n_repeats=5, random_state=RANDOM_STATE, n_jobs=1)
    imp = pd.DataFrame({"feature": num + cat, "importance": pi.importances_mean, "std": pi.importances_std}).sort_values("importance", ascending=False)
    save_table(imp, "risk_feature_importance")
    m["top_features"] = imp.feature.head(6).tolist()

    te["bin"] = pd.cut(te.p, bins=[0, 0.02, 0.04, 0.06, 0.08, 0.12, 0.2, 0.35, 1.0], include_lowest=True)
    calib = te.groupby("bin", observed=True).agg(n=("y", "size"), predicted=("p", "mean"), actual=("y", "mean")).reset_index()
    calib["bin"] = calib.bin.astype(str)
    save_table(calib, "risk_calibration")

    df["p_late"] = gbm.predict_proba(df[num + cat])[:, 1]
    save_table(df[["order_id", "purchase_date", "is_late", "p_late", "seller_id", "customer_state", "distance_km", "promised_days"]], "risk_scores")

    # ---- figures ------------------------------------------------------------
    fpr, tpr, _ = roc_curve(y_te, p)
    fpr2, tpr2, _ = roc_curve(y_te, p_lr)
    fig, ax = new_fig(5.5, 5)
    ax.plot(fpr, tpr, color=PALETTE[0], label=f"Gradient boosting (AUC {m['gbm_auc']:.3f})")
    ax.plot(fpr2, tpr2, color=PALETTE[1], label=f"Logistic regression (AUC {m['lr_auc']:.3f})")
    ax.plot([0, 1], [0, 1], color="#9a9995", lw=1, ls="--")
    ax.set_xlabel("false positive rate"); ax.set_ylabel("true positive rate")
    ax.set_title("Late-delivery risk: ROC on Mar-Jul 2018 holdout")
    ax.legend(loc="lower right")
    save(fig, "21_risk_roc")

    fig, ax = new_fig(8, 4)
    ax.bar(lift.decile.astype(str), lift.late_rate, color=PALETTE[0])
    ax.axhline(base, color=PALETTE[1], lw=1.2, ls="--")
    ax.text(9.5, base, f" base {base:.1%}", color=PALETTE[1], fontsize=8, va="bottom", ha="right")
    fmt_pct(ax)
    ax.set_xlabel("risk decile (1 = highest predicted risk)")
    ax.set_title("Actual late rate by predicted-risk decile (holdout)")
    save(fig, "22_risk_lift")

    top = imp.head(12).iloc[::-1]
    fig, ax = new_fig(8, 4.5)
    ax.barh(top.feature, top.importance, xerr=top["std"], color=PALETTE[0], height=0.6, ecolor="#9a9995")
    ax.grid(axis="x"); ax.grid(False, axis="y")
    ax.set_title("Late-delivery drivers: permutation importance (holdout AUC drop)")
    save(fig, "23_risk_importance")

    fig, ax = new_fig(5.5, 5)
    ax.plot(calib.predicted, calib.actual, marker="o", color=PALETTE[0])
    ax.plot([0, calib.actual.max()], [0, calib.actual.max()], color="#9a9995", lw=1, ls="--")
    ax.set_xlabel("mean predicted P(late)"); ax.set_ylabel("actual late rate")
    ax.set_title("Calibration (holdout)")
    save(fig, "24_risk_calibration")
    return m
