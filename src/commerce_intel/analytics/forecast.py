"""Weekly GMV forecasting with a rolling-origin backtest (seasonal naive vs Holt-Winters vs SARIMA)."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

from ..config import ANALYSIS_START, FORECAST_END, PALETTE
from ..db import query
from ..viz import fmt_thousands, new_fig, save
from ._common import save_table

warnings.filterwarnings("ignore")
H = 8          # forecast horizon (weeks)
N_FOLDS = 6    # rolling-origin folds


def weekly(con) -> pd.Series:
    df = query(
        con,
        f"""
        select date_trunc('week', purchase_date) wk, sum(gmv) gmv, count(*) orders
        from marts.fact_orders
        where purchase_date between date '{ANALYSIS_START}' and date '{FORECAST_END}' and not is_cancelled
        group by 1 order by 1
        """,
    )
    s = df.set_index(pd.to_datetime(df.wk)).gmv.asfreq("W-MON")
    # first week (starts 2016-12-26) is partial; FORECAST_END is a Sunday so the last week is complete
    return s.iloc[1:].interpolate()


def _wape(a, f):
    return float(np.abs(a - f).sum() / np.abs(a).sum())


def fit_predict(train: pd.Series, h: int) -> dict[str, np.ndarray]:
    out = {}
    out["naive_last4w_mean"] = np.array([train.iloc[-4:].mean()] * h)  # mean of last 4 weeks
    hw = ExponentialSmoothing(train, trend="add", damped_trend=True, seasonal=None).fit(optimized=True)
    out["holt_damped"] = np.asarray(hw.forecast(h))
    # Black Friday week is an outlier; model in logs with a damped trend + AR(1) errors
    sar = SARIMAX(np.log(train), order=(1, 1, 1), trend="c", enforce_stationarity=False, enforce_invertibility=False).fit(disp=0)
    out["sarima_log"] = np.exp(np.asarray(sar.forecast(h)))
    return out


def run(con) -> dict:
    s = weekly(con)
    rows = []
    for k in range(N_FOLDS, 0, -1):
        cut = len(s) - k * H if k > 1 else len(s) - H
        cut = len(s) - H - (k - 1) * 4  # origins 4 weeks apart
        train, test = s.iloc[:cut], s.iloc[cut: cut + H]
        if len(test) < H:
            continue
        preds = fit_predict(train, H)
        for name, p in preds.items():
            rows.append({"fold_origin": str(train.index[-1].date()), "model": name, "wape": _wape(test.values, p),
                         "bias": float((p - test.values).sum() / test.values.sum())})
    bt = pd.DataFrame(rows)
    summary = bt.groupby("model").agg(wape_mean=("wape", "mean"), wape_median=("wape", "median"), bias_mean=("bias", "mean")).sort_values("wape_mean")
    save_table(bt, "forecast_backtest_folds")
    save_table(summary.reset_index(), "forecast_backtest_summary")
    best = summary.index[0]

    # final 8-week forecast from full history (excluding the data-truncation tail)
    full_preds = fit_predict(s, H)
    idx = pd.date_range(s.index[-1] + pd.Timedelta(weeks=1), periods=H, freq="W-MON")
    fc = pd.DataFrame({m: v for m, v in full_preds.items()}, index=idx)
    fc.index.name = "week"
    save_table(fc.reset_index(), "forecast_next_8_weeks")
    hist = s.rename("gmv").reset_index().rename(columns={"index": "week", "wk": "week"})
    save_table(hist, "forecast_weekly_history")

    # ---- figure -------------------------------------------------------------
    fig, ax = new_fig(10, 4.2)
    ax.plot(s.index, s.values, color=PALETTE[0], label="Weekly GMV (actual)")
    ax.plot(fc.index, fc[best], color=PALETTE[1], ls="--", marker="o", ms=3, label=f"{best} forecast (+{H} wks)")
    # show last backtest fold
    cut = len(s) - H
    p = fit_predict(s.iloc[:cut], H)[best]
    ax.plot(s.index[cut:], p, color=PALETTE[2], ls=":", lw=2, label=f"backtest, last fold (WAPE {_wape(s.values[cut:], p):.1%})")
    fmt_thousands(ax, prefix="R$")
    ax.set_title(f"Weekly GMV: best of 3 models on a {N_FOLDS}-fold rolling backtest is '{best}' (mean WAPE {summary.wape_mean.iloc[0]:.1%})")
    ax.legend(loc="upper left")
    save(fig, "25_weekly_forecast")

    return {
        "weeks": int(len(s)),
        "horizon_weeks": H,
        "folds": int(bt.fold_origin.nunique()),
        "best_model": best,
        "backtest_wape": {m: float(v) for m, v in summary.wape_mean.items()},
        "backtest_bias": {m: float(v) for m, v in summary.bias_mean.items()},
        "next_8w_gmv_best": float(fc[best].sum()),
        "last_8w_gmv_actual": float(s.iloc[-H:].sum()),
        "avg_weekly_gmv_last_12w": float(s.iloc[-12:].mean()),
        "peak_week": str(s.idxmax().date()),
        "peak_week_gmv": float(s.max()),
    }
