"""RFM scoring + K-means behavioural segments, with a profile of each segment."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from ..config import ANALYSIS_END, ANALYSIS_START, PALETTE, RANDOM_STATE, SNAPSHOT_DATE
from ..db import query
from ..viz import fmt_thousands, new_fig, save
from ._common import save_table

# Rules tuned for a marketplace where ~97% of buyers have a single order:
# frequency separates repeaters, recency separates live from lapsed, monetary flags value.
SEGMENT_RULES = [
    ("Champions",          lambda r, f, m: f >= 2 and r >= 4),   # recent repeat buyers
    ("At Risk",            lambda r, f, m: f >= 2),              # repeat buyers gone quiet
    ("High-Value New",     lambda r, f, m: m == 5 and r >= 4),   # one big recent order
    ("Lapsed High-Value",  lambda r, f, m: m >= 4 and r <= 2),   # win-back targets
    ("Promising",          lambda r, f, m: r >= 4),              # recent one-timers
    ("Need Attention",     lambda r, f, m: r == 3),
    ("Hibernating",        lambda r, f, m: True),
]


def rfm_table(con) -> pd.DataFrame:
    df = query(
        con,
        f"""
        select customer_unique_id,
               date_diff('day', max(purchase_date), date '{SNAPSHOT_DATE}') as recency_days,
               count(*)                                                   as frequency,
               sum(gmv)                                                   as monetary,
               avg(review_score)                                          as avg_review,
               max(customer_state)                                        as state
        from marts.fact_orders
        where purchase_date between date '{ANALYSIS_START}' and date '{ANALYSIS_END}' and not is_cancelled
        group by 1
        """,
    )
    # R: lower recency better. F is extremely skewed (97% = 1 order) -> use rank-based bands with ties handled.
    df["r_score"] = pd.qcut(df.recency_days.rank(method="first", ascending=False), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    df["f_score"] = np.select([df.frequency >= 4, df.frequency == 3, df.frequency == 2], [5, 4, 2], default=1)
    df["m_score"] = pd.qcut(df.monetary.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    df["rfm"] = df.r_score.astype(str) + df.f_score.astype(str) + df.m_score.astype(str)

    def label(row):
        for name, rule in SEGMENT_RULES:
            if rule(row.r_score, row.f_score, row.m_score):
                return name
        return "Other"

    df["segment"] = df.apply(label, axis=1)
    return df


def kmeans_segments(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    X = df[["recency_days", "frequency", "monetary"]].copy()
    X["frequency"] = np.log1p(X.frequency)
    X["monetary"] = np.log1p(X.monetary)
    Xs = StandardScaler().fit_transform(X)
    rng = np.random.default_rng(RANDOM_STATE)
    sample = rng.choice(len(Xs), size=min(15000, len(Xs)), replace=False)
    scores = {}
    for k in range(3, 8):
        km = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE).fit(Xs)
        scores[k] = float(silhouette_score(Xs[sample], km.labels_[sample]))
    best_k = max(scores, key=scores.get)
    km = KMeans(n_clusters=best_k, n_init=10, random_state=RANDOM_STATE).fit(Xs)
    df = df.copy()
    df["cluster"] = km.labels_
    prof = df.groupby("cluster").agg(customers=("customer_unique_id", "count"), recency=("recency_days", "median"),
                                     frequency=("frequency", "mean"), monetary=("monetary", "median"),
                                     gmv=("monetary", "sum")).sort_values("monetary", ascending=False)
    return df, {"k": best_k, "silhouette": scores[best_k], "all_scores": scores, "profile": prof}


def run(con) -> dict:
    df = rfm_table(con)
    df, km = kmeans_segments(df)
    save_table(df, "rfm_customers")

    prof = (
        df.groupby("segment")
        .agg(customers=("customer_unique_id", "count"), gmv=("monetary", "sum"), avg_monetary=("monetary", "mean"),
             avg_frequency=("frequency", "mean"), median_recency=("recency_days", "median"), avg_review=("avg_review", "mean"))
        .sort_values("gmv", ascending=False)
    )
    prof["customer_share"] = prof.customers / prof.customers.sum()
    prof["gmv_share"] = prof.gmv / prof.gmv.sum()
    prof["gmv_index"] = prof.gmv_share / prof.customer_share
    save_table(prof.reset_index(), "rfm_segment_profile")
    save_table(km["profile"].reset_index(), "kmeans_cluster_profile")

    # ---- figures ------------------------------------------------------------
    p = prof.sort_values("customers")
    fig, ax = new_fig(9, 4.6)
    y = np.arange(len(p))
    ax.barh(y - 0.2, p.customer_share, height=0.38, color=PALETTE[0], label="Share of customers")
    ax.barh(y + 0.2, p.gmv_share, height=0.38, color=PALETTE[1], label="Share of GMV")
    ax.set_yticks(y, p.index)
    ax.grid(axis="x"); ax.grid(False, axis="y")
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_title("RFM segments: customers vs. GMV share")
    ax.legend(loc="lower right")
    save(fig, "07_rfm_segments")

    fig, ax = new_fig(8, 4.5)
    s = df.sample(min(20000, len(df)), random_state=RANDOM_STATE)
    for i, c in enumerate(sorted(s.cluster.unique())):
        sub = s[s.cluster == c]
        ax.scatter(sub.recency_days, sub.monetary, s=6, alpha=0.5, color=PALETTE[i % len(PALETTE)], label=f"cluster {c}")
    ax.set_yscale("log")
    ax.set_xlabel("recency (days since last order)")
    ax.set_ylabel("monetary (BRL, log)")
    ax.set_title(f"K-means clusters (k={km['k']}, silhouette {km['silhouette']:.2f})")
    ax.legend(markerscale=3)
    save(fig, "08_kmeans_clusters")

    champ = prof.loc["Champions"] if "Champions" in prof.index else None
    lapsed_hv = prof.loc["Lapsed High-Value"] if "Lapsed High-Value" in prof.index else None
    return {
        "n_customers_scored": int(len(df)),
        "segments": {k: {"customers": int(v.customers), "gmv_share": float(v.gmv_share), "gmv_index": float(v.gmv_index)}
                     for k, v in prof.iterrows()},
        "champions_customer_share": float(champ.customer_share) if champ is not None else None,
        "champions_gmv_share": float(champ.gmv_share) if champ is not None else None,
        "lapsed_high_value_customers": int(lapsed_hv.customers) if lapsed_hv is not None else None,
        "lapsed_high_value_gmv_share": float(lapsed_hv.gmv_share) if lapsed_hv is not None else None,
        "hibernating_customer_share": float(prof.loc["Hibernating", "customer_share"]) if "Hibernating" in prof.index else None,
        "kmeans_k": km["k"],
        "kmeans_silhouette": km["silhouette"],
        "one_time_buyer_share": float((df.frequency == 1).mean()),
    }
