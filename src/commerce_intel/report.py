"""Build the interactive HTML dashboard (single file, Plotly via CDN) from the analysis tables + results.json."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .config import DIVERGING, PALETTE, REPORTS_DIR, RESULTS_JSON, ROOT, SEQUENTIAL, SURFACE, TABLE_DIR, TEXT_PRIMARY, TEXT_SECONDARY

LAYOUT = dict(
    paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
    font=dict(family="Inter, Segoe UI, Helvetica, Arial, sans-serif", size=12, color=TEXT_PRIMARY),
    margin=dict(l=50, r=20, t=50, b=40),
    title=dict(x=0, xanchor="left", font=dict(size=14)),
    xaxis=dict(showgrid=False, zeroline=False, linecolor="#e6e5e1"),
    yaxis=dict(gridcolor="#e6e5e1", zeroline=False),
    hoverlabel=dict(bgcolor="white", font_size=12),
    legend=dict(orientation="h", y=1.08, x=0, bgcolor="rgba(0,0,0,0)"),
    colorway=PALETTE,
)


def _t(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLE_DIR / f"{name}.csv")


def _fig(fig: go.Figure, height: int = 380) -> str:
    fig.update_layout(**LAYOUT, height=height)
    return fig.to_html(include_plotlyjs=False, full_html=False, config={"displaylogo": False, "responsive": True})


def _tile(label: str, value: str, sub: str = "") -> str:
    return f'<div class="tile"><div class="tile-label">{label}</div><div class="tile-value">{value}</div><div class="tile-sub">{sub}</div></div>'


def _money(v: float) -> str:
    return f"R${v / 1e6:.2f}M" if v >= 1e6 else f"R${v / 1e3:.0f}K" if v >= 1e3 else f"R${v:,.0f}"


def build() -> Path:
    R = json.loads(RESULTS_JSON.read_text())
    k, ret, seg, clv, dlv, sel, fun, fc, geo, risk, prop, exp = (
        R["kpis"], R["retention"], R["segmentation"], R["clv"], R["delivery"], R["sellers"], R["funnel"],
        R["forecast"], R["geo"], R["risk_model"], R["propensity"], R["experiment"])
    charts: dict[str, str] = {}

    # ---------------- growth ----------------
    m = _t("kpi_monthly")
    f = go.Figure(go.Bar(x=m.purchase_month, y=m.gmv, marker_color=PALETTE[0], name="GMV",
                         hovertemplate="%{x}<br>GMV R$%{y:,.0f}<extra></extra>"))
    f.update_layout(title="Monthly GMV (BRL)")
    f.update_xaxes(type="category", tickangle=-45)
    f.update_yaxes(tickprefix="R$", tickformat="~s")
    charts["gmv"] = _fig(f)

    f = go.Figure()
    f.add_trace(go.Scatter(x=m.purchase_month, y=m.customers, name="Ordering customers", mode="lines+markers", line=dict(color=PALETTE[0], width=2), marker=dict(size=5)))
    f.add_trace(go.Scatter(x=m.purchase_month, y=m.active_sellers, name="Active sellers", mode="lines+markers", line=dict(color=PALETTE[1], width=2), marker=dict(size=5)))
    f.update_layout(title="Monthly active customers vs. sellers (log scale)")
    f.update_yaxes(type="log")
    charts["cust_sellers"] = _fig(f)

    cat = _t("kpi_category").head(12).iloc[::-1]
    f = go.Figure(go.Bar(y=cat.category.str.replace("_", " "), x=cat.gmv, orientation="h", marker_color=PALETTE[0],
                         text=[f"{s:.1%}" for s in cat.gmv_share], textposition="outside",
                         hovertemplate="%{y}<br>GMV R$%{x:,.0f}<extra></extra>"))
    f.update_layout(title="Top 12 categories by GMV (share of total)")
    f.update_xaxes(tickprefix="R$", tickformat="~s", showgrid=True, gridcolor="#e6e5e1")
    f.update_yaxes(showgrid=False)
    charts["category"] = _fig(f, 420)

    pay = _t("kpi_payment_type")
    f = go.Figure(go.Bar(x=pay.payment_type, y=pay.value_share, marker_color=PALETTE[0], text=[f"{v:.1%}" for v in pay.value_share], textposition="outside"))
    f.update_layout(title="Payment mix (share of value)")
    f.update_yaxes(tickformat=".0%")
    charts["payments"] = _fig(f, 320)

    inst = _t("kpi_installments")
    f = go.Figure(go.Bar(x=inst.installments_band, y=inst.aov, marker_color=PALETTE[0], text=[f"R${v:,.0f}" for v in inst.aov], textposition="outside"))
    f.update_layout(title="Average order value by number of installments")
    f.update_yaxes(tickprefix="R$")
    charts["installments"] = _fig(f, 320)

    # ---------------- customers ----------------
    rm = pd.read_csv(TABLE_DIR / "retention_matrix.csv", index_col=0)
    rm = rm.iloc[:, 1:13]
    z = rm.values * 100
    f = go.Figure(go.Heatmap(z=z, x=[f"M{c}" for c in rm.columns], y=rm.index, colorscale=[[0, SEQUENTIAL[0]], [1, SEQUENTIAL[-1]]],
                             text=np.where(np.isnan(z), "", np.round(z, 1)), texttemplate="%{text}", textfont=dict(size=9),
                             hovertemplate="cohort %{y}, month %{x}: %{z:.2f}% retained<extra></extra>", colorbar=dict(title="%")))
    f.update_layout(title="Monthly cohort retention (% of cohort placing another order)")
    f.update_yaxes(autorange="reversed", showgrid=False)
    charts["cohorts"] = _fig(f, 520)

    sp = _t("rfm_segment_profile").sort_values("customers")
    f = go.Figure()
    f.add_trace(go.Bar(y=sp.segment, x=sp.customer_share, orientation="h", name="Share of customers", marker_color=PALETTE[0]))
    f.add_trace(go.Bar(y=sp.segment, x=sp.gmv_share, orientation="h", name="Share of GMV", marker_color=PALETTE[1]))
    f.update_layout(title="RFM segments: customers vs. GMV", barmode="group")
    f.update_xaxes(tickformat=".0%", showgrid=True, gridcolor="#e6e5e1")
    f.update_yaxes(showgrid=False)
    charts["rfm"] = _fig(f, 400)

    dec = _t("clv_deciles")
    f = go.Figure(go.Bar(x=dec.decile.astype(str), y=dec.clv_share, marker_color=PALETTE[0], text=[f"{v:.0%}" for v in dec.clv_share], textposition="outside"))
    f.update_layout(title="Predicted 12-month CLV: share of value by decile (1 = highest)")
    f.update_yaxes(tickformat=".0%")
    charts["clv"] = _fig(f, 320)

    gap = _t("retention_repeat_by_first_category")
    gap = gap[gap.category != "unknown"].head(10)
    f = go.Figure(go.Bar(x=gap.category.str.replace("_", " "), y=gap.repeat_rate, marker_color=PALETTE[0], text=[f"{v:.1%}" for v in gap.repeat_rate], textposition="outside"))
    f.update_layout(title="Repeat-customer rate by first-order category (top 10, >=500 customers)")
    f.update_yaxes(tickformat=".0%")
    charts["repeat_cat"] = _fig(f, 340)

    # ---------------- delivery & CX ----------------
    b = _t("delivery_bucket_reviews")
    f = go.Figure(go.Bar(x=b.delivery_bucket.str[3:], y=b.avg_review, marker_color=[PALETTE[2] if i < 3 else PALETTE[7] for i in range(len(b))],
                         text=[f"{v:.2f}<br>{s:.1%} of orders" for v, s in zip(b.avg_review, b.share)], textposition="outside"))
    f.update_layout(title="Average review score by delivery outcome vs. promised date")
    f.update_yaxes(range=[0, 5.6])
    charts["delivery_reviews"] = _fig(f, 380)

    dm = _t("delivery_monthly")
    f = go.Figure(go.Scatter(x=dm.purchase_month, y=dm.late_rate, mode="lines+markers", line=dict(color=PALETTE[1], width=2), marker=dict(size=6),
                             hovertemplate="%{x}: %{y:.1%} late<extra></extra>"))
    f.update_layout(title="Share of delivered orders arriving after the promised date")
    f.update_yaxes(tickformat=".0%")
    charts["late_monthly"] = _fig(f, 320)

    orr = _t("delivery_logit_odds_ratios")
    orr = orr[orr.term != "Intercept"].sort_values("odds_ratio")
    f = go.Figure(go.Scatter(x=orr.odds_ratio, y=orr.term, mode="markers", marker=dict(size=9, color=PALETTE[0]),
                             error_x=dict(type="data", symmetric=False, array=orr.ci_high - orr.odds_ratio, arrayminus=orr.odds_ratio - orr.ci_low, color="#9a9995"),
                             hovertemplate="%{y}: OR %{x:.2f}<extra></extra>"))
    f.add_vline(x=1, line_dash="dash", line_color="#9a9995")
    f.update_layout(title="Drivers of a 1-2 star review: odds ratios, 95% CI")
    f.update_xaxes(type="log", showgrid=True, gridcolor="#e6e5e1")
    f.update_yaxes(showgrid=False)
    charts["odds"] = _fig(f, 400)

    st = _t("delivery_by_state").head(15)
    f = go.Figure(go.Bar(x=st.state, y=st.avg_delivery_days, marker_color=PALETTE[0], text=[f"{v:.0f}d" for v in st.avg_delivery_days], textposition="outside",
                         customdata=np.stack([st.late_rate, st.avg_promised_days], axis=1),
                         hovertemplate="%{x}: %{y:.1f} days actual, %{customdata[1]:.0f} promised, %{customdata[0]:.1%} late<extra></extra>"))
    f.update_layout(title="Average delivery days by customer state (15 largest states)")
    charts["delivery_state"] = _fig(f, 320)

    # ---------------- sellers ----------------
    sc = _t("seller_scorecard")
    f = go.Figure()
    f.add_trace(go.Scatter(x=sc.seller_pct, y=sc.cum_gmv_share, mode="lines", line=dict(color=PALETTE[0], width=2), name="Cumulative GMV share", hovertemplate="top %{x:.0%} of sellers = %{y:.0%} of GMV<extra></extra>"))
    f.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color="#9a9995", dash="dash", width=1), name="Perfect equality"))
    f.update_layout(title=f"Seller concentration (Gini {sel['gini']:.2f})")
    f.update_xaxes(tickformat=".0%", title="share of sellers, ranked by GMV")
    f.update_yaxes(tickformat=".0%")
    charts["pareto"] = _fig(f, 380)

    tiers = _t("seller_tiers")
    f = go.Figure(go.Bar(x=tiers.tier, y=tiers.gmv_share, marker_color=[PALETTE[7], PALETTE[1], PALETTE[0], PALETTE[2]][: len(tiers)],
                         text=[f"{g:.0%} of GMV<br>{n} sellers" for g, n in zip(tiers.gmv_share, tiers.sellers)], textposition="outside",
                         customdata=np.stack([tiers.avg_late, tiers.avg_review], axis=1), hovertemplate="%{x}<br>late %{customdata[0]:.1%}, review %{customdata[1]:.2f}<extra></extra>"))
    f.update_layout(title="Seller health tiers (score = 50% volume, 25% on-time, 25% reviews)")
    f.update_yaxes(tickformat=".0%", range=[0, tiers.gmv_share.max() * 1.3])
    charts["tiers"] = _fig(f, 360)

    sa = pd.read_csv(TABLE_DIR / "seller_cohort_activity.csv", index_col=0).mean()
    f = go.Figure(go.Scatter(x=[f"M{i}" for i in sa.index], y=sa.values, mode="lines+markers", line=dict(color=PALETTE[0], width=2), marker=dict(size=7)))
    f.update_layout(title="Share of a seller cohort still selling N months after first sale")
    f.update_yaxes(tickformat=".0%")
    charts["seller_activity"] = _fig(f, 320)

    # ---------------- funnel ----------------
    f = go.Figure(go.Funnel(y=["Marketing-qualified leads", "Closed deals", "Activated sellers (>=1 sale)"],
                            x=[fun["mqls"], fun["deals"], fun["activated"]], marker_color=[PALETTE[0], PALETTE[0], PALETTE[0]],
                            textinfo="value+percent previous", connector=dict(line=dict(color="#e6e5e1"))))
    f.update_layout(title="Seller acquisition funnel")
    charts["funnel"] = _fig(f, 320)

    ch = _t("funnel_by_channel")
    ch = ch[(ch.mqls >= 100) & (ch.origin != "unknown")].sort_values("gmv_per_mql")
    f = go.Figure(go.Bar(y=ch.origin, x=ch.gmv_per_mql, orientation="h", marker_color=PALETTE[0], text=[f"R${v:,.0f}" for v in ch.gmv_per_mql], textposition="outside",
                         customdata=np.stack([ch.mqls, ch.close_rate, ch.mql_to_active], axis=1),
                         hovertemplate="%{y}<br>%{customdata[0]:,} MQLs, close rate %{customdata[1]:.1%}, MQL->active %{customdata[2]:.1%}<br>GMV per MQL R$%{x:,.0f}<extra></extra>"))
    f.update_layout(title="GMV generated per lead, by acquisition channel (>=100 MQLs; unknown source excluded)")
    f.update_xaxes(tickprefix="R$", showgrid=True, gridcolor="#e6e5e1")
    f.update_yaxes(showgrid=False)
    charts["channel"] = _fig(f, 380)

    sg = _t("funnel_by_segment").head(10)
    f = go.Figure(go.Bar(x=sg.business_segment, y=sg.gmv, marker_color=PALETTE[0], customdata=np.stack([sg.deals, sg.activation_rate], axis=1),
                         hovertemplate="%{x}<br>GMV R$%{y:,.0f}<br>%{customdata[0]} deals, %{customdata[1]:.0%} activated<extra></extra>"))
    f.update_layout(title="GMV from acquired sellers by declared business segment (top 10)")
    f.update_yaxes(tickprefix="R$", tickformat="~s")
    charts["segment"] = _fig(f, 320)

    # ---------------- geo ----------------
    pts = _t("geo_points")
    pts = pts[pts.orders >= 3]
    f = go.Figure(go.Scattergeo(lon=pts.lng, lat=pts.lat, mode="markers",
                                marker=dict(size=np.sqrt(pts.gmv) / 12, sizemin=2, color=pts.avg_delivery_days.clip(upper=30),
                                            colorscale=[[0, SEQUENTIAL[0]], [1, SEQUENTIAL[-1]]], opacity=0.6, line_width=0,
                                            colorbar=dict(title="avg delivery<br>days")),
                                text=pts.city.str.title() + ", " + pts.state, customdata=np.stack([pts.orders, pts.gmv, pts.avg_delivery_days], axis=1),
                                hovertemplate="%{text}<br>%{customdata[0]} orders, R$%{customdata[1]:,.0f}<br>%{customdata[2]:.1f} delivery days<extra></extra>"))
    f.update_geos(scope="south america", showcountries=True, countrycolor="#d4d4d0", showland=True, landcolor="#f4f3ef", showocean=False,
                  lataxis_range=[-34, 6], lonaxis_range=[-74, -34], bgcolor=SURFACE)
    f.update_layout(title="Demand map: bubble = GMV, colour = average delivery days", geo=dict(projection_type="mercator"))
    charts["map"] = _fig(f, 560)

    gs = _t("geo_state").head(15)
    f = go.Figure(go.Bar(x=gs.state, y=gs.gmv_share, marker_color=PALETTE[0], text=[f"{v:.1%}" for v in gs.gmv_share], textposition="outside",
                         customdata=np.stack([gs.aov, gs.freight_ratio, gs.late_rate], axis=1),
                         hovertemplate="%{x}: %{y:.1%} of GMV<br>AOV R$%{customdata[0]:.0f}, freight/price %{customdata[1]:.0%}, late %{customdata[2]:.1%}<extra></extra>"))
    f.update_layout(title="GMV share by customer state (top 15)")
    f.update_yaxes(tickformat=".0%")
    charts["state"] = _fig(f, 320)

    # ---------------- forecast ----------------
    hist = _t("forecast_weekly_history")
    fcst = _t("forecast_next_8_weeks")
    best = fc["best_model"]
    f = go.Figure()
    f.add_trace(go.Scatter(x=hist.week, y=hist.gmv, mode="lines", name="Weekly GMV", line=dict(color=PALETTE[0], width=2)))
    f.add_trace(go.Scatter(x=fcst.week, y=fcst[best], mode="lines+markers", name=f"Forecast ({best})", line=dict(color=PALETTE[1], width=2, dash="dash")))
    for i, mname in enumerate([c for c in fcst.columns if c not in ("week", best)]):
        f.add_trace(go.Scatter(x=fcst.week, y=fcst[mname], mode="lines", name=mname, line=dict(color=PALETTE[2 + i], width=1.5, dash="dot"), visible="legendonly"))
    f.update_layout(title=f"Weekly GMV and 8-week forecast (backtest WAPE: {', '.join(f'{kk} {v:.1%}' for kk, v in fc['backtest_wape'].items())})", legend=dict(y=1.12))
    f.update_yaxes(tickprefix="R$", tickformat="~s")
    charts["forecast"] = _fig(f, 380)

    # ---------------- models ----------------
    rl = _t("risk_decile_lift")
    f = go.Figure(go.Bar(x=rl.decile.astype(str), y=rl.late_rate, marker_color=PALETTE[0], text=[f"{v:.1%}" for v in rl.late_rate], textposition="outside",
                         customdata=rl.cum_capture, hovertemplate="decile %{x}: %{y:.1%} late, captures %{customdata:.0%} of all late orders cumulatively<extra></extra>"))
    f.add_hline(y=risk["test_late_rate"], line_dash="dash", line_color=PALETTE[1], annotation_text=f"base {risk['test_late_rate']:.1%}", annotation_position="top right")
    f.update_layout(title=f"Late-delivery risk: actual late rate by predicted-risk decile (holdout, AUC {risk['gbm_auc']:.2f})")
    f.update_yaxes(tickformat=".0%")
    charts["risk_lift"] = _fig(f, 340)

    ri = _t("risk_feature_importance").head(10).iloc[::-1]
    f = go.Figure(go.Bar(y=ri.feature, x=ri.importance, orientation="h", marker_color=PALETTE[0], error_x=dict(type="data", array=ri["std"], color="#9a9995")))
    f.update_layout(title="What predicts lateness at checkout? Permutation importance (AUC drop)")
    f.update_xaxes(showgrid=True, gridcolor="#e6e5e1")
    f.update_yaxes(showgrid=False)
    charts["risk_imp"] = _fig(f, 360)

    rc = _t("risk_calibration")
    f = go.Figure()
    f.add_trace(go.Scatter(x=rc.predicted, y=rc.actual, mode="lines+markers", name="model", line=dict(color=PALETTE[0], width=2), marker=dict(size=7), customdata=rc.n, hovertemplate="pred %{x:.1%} -> actual %{y:.1%} (n=%{customdata})<extra></extra>"))
    mx = max(rc.actual.max(), rc.predicted.max())
    f.add_trace(go.Scatter(x=[0, mx], y=[0, mx], mode="lines", name="perfect", line=dict(color="#9a9995", dash="dash", width=1)))
    f.update_layout(title="Calibration: predicted vs. actual late rate")
    f.update_xaxes(tickformat=".0%"); f.update_yaxes(tickformat=".0%")
    charts["risk_cal"] = _fig(f, 340)

    pl = _t("propensity_decile_lift")
    f = go.Figure(go.Bar(x=pl.decile.astype(str), y=pl.lift, marker_color=PALETTE[0], text=[f"{v:.2f}x" for v in pl.lift], textposition="outside"))
    f.add_hline(y=1, line_dash="dash", line_color="#9a9995")
    f.update_layout(title=f"Repeat-purchase propensity: lift by decile (AUC {prop['champion_auc']:.2f} - weak signal, see note)")
    charts["prop_lift"] = _fig(f, 320)

    ex = _t("experiment_plan")
    rows = "".join(
        f"<tr><td><b>{r.test}</b><br><span class='muted'>{r.hypothesis}</span></td><td>{r.metric}</td>"
        f"<td>{r.baseline:.1%}</td><td>{r.mde_relative:+.0%}</td><td>{int(r.n_per_arm):,}</td>"
        f"<td>{'' if pd.isna(r.weeks_to_run) else int(r.weeks_to_run)}</td><td>{'yes' if r.feasible else 'no - needs longer run or bigger MDE'}</td></tr>"
        if r.metric != "average order value" else
        f"<tr><td><b>{r.test}</b><br><span class='muted'>{r.hypothesis}</span></td><td>{r.metric}</td>"
        f"<td>R${r.baseline:,.0f}</td><td>{r.mde_relative:+.0%}</td><td>{int(r.n_per_arm):,}</td>"
        f"<td>{'' if pd.isna(r.weeks_to_run) else int(r.weeks_to_run)}</td><td>{'yes' if r.feasible else 'no - needs longer run or bigger MDE'}</td></tr>"
        for r in ex.itertuples())
    exp_table = f"""<table class="tbl"><thead><tr><th>Test</th><th>Primary metric</th><th>Baseline</th><th>MDE (relative)</th>
        <th>n per arm (80% power, α=0.05)</th><th>Weeks at 2018 volume</th><th>Feasible in 12 weeks?</th></tr></thead><tbody>{rows}</tbody></table>"""

    # ---------------- HTML ----------------
    tiles = "".join([
        _tile("GMV (Jan-17 to Jul-18)", _money(k["gmv_total"]), f"{k['gmv_yoy_ytd']:+.0%} YoY, Jan-Jul"),
        _tile("Orders", f"{k['orders']:,}", f"{k['orders_yoy_ytd']:+.0%} YoY, Jan-Jul"),
        _tile("Customers", f"{k['customers']:,}", f"{ret['repeat_customer_rate']:.1%} ordered twice+"),
        _tile("Average order value", f"R${k['aov']:.0f}", f"{k['items_per_order']:.2f} items/order"),
        _tile("Late deliveries", f"{k['late_rate']:.1%}", f"peak {dlv['worst_late_month_rate']:.0%} in {dlv['worst_late_month']}"),
        _tile("Avg review", f"{k['avg_review']:.2f} / 5", f"{dlv['review_on_time']:.2f} on time vs {dlv['review_late']:.2f} late"),
        _tile("Active sellers", f"{k['sellers']:,}", f"top 10% = {sel['top10pct_gmv_share']:.0%} of GMV"),
        _tile("Lead -> active seller", f"{fun['mql_to_active']:.1%}", f"{fun['mqls']:,} MQLs -> {fun['activated']} selling"),
    ])

    def sec(id_, title, intro, *blocks):
        return f'<section id="{id_}"><h2>{title}</h2><p class="intro">{intro}</p>{"".join(blocks)}</section>'

    def grid(*cs):
        return '<div class="grid">' + "".join(f'<div class="card">{c}</div>' for c in cs) + "</div>"

    def card(c):
        return f'<div class="card">{c}</div>'

    def finding(text):
        return f'<div class="finding">{text}</div>'

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Commerce Intelligence Platform - Olist marketplace analytics</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
:root{{--bg:{SURFACE};--ink:{TEXT_PRIMARY};--muted:{TEXT_SECONDARY};--line:#e6e5e1;--blue:{PALETTE[0]};--orange:{PALETTE[1]}}}
*{{box-sizing:border-box}} body{{margin:0;background:#f4f3ef;color:var(--ink);font-family:Inter,"Segoe UI",Helvetica,Arial,sans-serif;line-height:1.45}}
header{{background:var(--bg);border-bottom:1px solid var(--line);padding:22px 28px}} header h1{{margin:0 0 4px;font-size:22px}} header p{{margin:0;color:var(--muted);font-size:14px}}
nav{{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:8px 28px;display:flex;gap:6px;flex-wrap:wrap}}
nav a{{text-decoration:none;color:var(--ink);font-size:13px;padding:6px 10px;border-radius:999px;border:1px solid var(--line)}} nav a:hover{{background:#eef4fc;border-color:var(--blue)}}
main{{max-width:1240px;margin:0 auto;padding:20px 24px 60px}}
section{{margin:26px 0}} h2{{font-size:18px;margin:0 0 6px}} .intro{{color:var(--muted);margin:0 0 14px;font-size:14px;max-width:960px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:16px 0}}
.tile{{background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:14px 16px}} .tile-label{{font-size:12px;color:var(--muted)}} .tile-value{{font-size:24px;font-weight:650;margin:2px 0}} .tile-sub{{font-size:12px;color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:14px}} .card{{background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:8px;min-width:0;overflow:hidden}} .card .plotly-graph-div{{width:100%!important}}
.finding{{background:#eef4fc;border-left:4px solid var(--blue);padding:10px 14px;border-radius:0 8px 8px 0;margin:12px 0;font-size:14px}}
.tbl{{width:100%;border-collapse:collapse;background:var(--bg);font-size:13px}} .tbl th,.tbl td{{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}} .tbl th{{color:var(--muted);font-weight:600;font-size:12px}}
.muted{{color:var(--muted)}} footer{{color:var(--muted);font-size:12px;text-align:center;padding:20px}}
ol.recs li{{margin:8px 0}} code{{background:#eee;padding:1px 5px;border-radius:4px;font-size:12px}}
</style></head><body>
<header><h1>Commerce Intelligence Platform</h1>
<p>End-to-end analytics on the Olist Brazilian marketplace (99K orders, 3K sellers, 8K seller leads) - dbt + DuckDB warehouse, Python models, Tableau / Power BI exports. Analysis window Jan-2017 to Jul-2018 (complete months; the extract is right-censored after mid-Aug-2018). Currency BRL.</p></header>
<nav><a href="#exec">Executive</a><a href="#growth">Growth</a><a href="#customers">Customers</a><a href="#cx">Delivery &amp; CX</a><a href="#sellers">Sellers</a><a href="#funnel">Seller acquisition</a><a href="#geo">Geography</a><a href="#forecast">Forecast</a><a href="#models">Models</a><a href="#recs">Recommendations</a></nav>
<main>
<section id="exec"><h2>Executive summary</h2><div class="tiles">{tiles}</div>
{finding(f"<b>Growth is real but one-shot.</b> GMV grew {k['gmv_yoy_ytd']:+.0%} year over year (Jan-Jul 2018 vs Jan-Jul 2017), yet only {ret['repeat_customer_rate']:.1%} of customers ever ordered twice and repeat orders are {ret['repeat_order_gmv_share']:.1%} of GMV. The marketplace is buying every real of revenue with new acquisition.")}
{finding(f"<b>Late delivery is the single biggest satisfaction lever.</b> On-time orders score {dlv['review_on_time']:.2f}; late ones {dlv['review_late']:.2f}. Being more than a week late multiplies the odds of a 1-2 star review by {dlv['odds_ratio_late_8p']:.0f}x. {dlv['late_share_of_all_detractors']:.0%} of all bad reviews come from the {dlv['late_rate']:.1%} of orders that arrive late; the model estimates ~{dlv['detractors_avoidable_if_on_time']:,.0f} detractor reviews were attributable to lateness.")}
{finding(f"<b>Supply is concentrated and leaky.</b> The top 10% of sellers generate {sel['top10pct_gmv_share']:.0%} of GMV (Gini {sel['gini']:.2f}); only {sel['seller_active_m6']:.0%} of a seller cohort is still selling six months after its first sale. In the B2B funnel, {fun['mql_to_active']:.1%} of marketing-qualified leads become sellers with at least one sale; paid search produces R${fun['paid_search_gmv_per_mql']:,.0f} of GMV per lead vs R${fun['social_gmv_per_mql']:,.0f} for social.")}
</section>
{sec("growth", "Growth", f"Monthly GMV grew from R${m.gmv.iloc[0] / 1e3:,.0f}K in Jan-2017 to a Black-Friday peak of {_money(k['black_friday_month_gmv'])} in Nov-2017 and plateaued around R$1.0-1.2M per month through 2018 (Jan-Jul 2018 vs Jan-Jul 2017: {k['gmv_yoy_ytd']:+.0%}). {k['top_category'].replace('_', ' ').title()} is the largest category at {k['top_category_share']:.1%}; the top 10 categories hold {k['top10_category_share']:.0%} of GMV. Credit cards carry {k['credit_card_value_share']:.0%} of payment value and the average order is split into {k['avg_installments']:.1f} installments.", grid(charts['gmv'], charts['cust_sellers']), grid(charts['category'], charts['payments'] + charts['installments']))}
{sec("customers", "Customers: retention, segments, lifetime value", f"Retention is the structural weakness. Average month-1 retention is {ret['month1_retention_avg']:.2%} and month-6 is {ret['month6_retention_avg']:.2%}; {ret['share_2nd_order_same_day']:.0%} of 'second orders' happen the same day (split checkouts, not loyalty) and the median gap to a true second order is {ret['median_days_to_2nd_order']:.0f} days. RFM segmentation shows {seg['segments']['Lapsed High-Value']['customers']:,} lapsed high-value customers holding {seg['lapsed_high_value_gmv_share']:.0%} of historical GMV - the natural win-back list. A BG/NBD model (holdout error {clv['holdout_error_pct']:+.0%} on total repeat purchases) expects only {clv['expected_repeat_purchases_12m_total']:,.0f} repeat purchases from the whole base in the next 12 months; the top CLV decile holds {clv['top_decile_clv_share']:.0%} of predicted value.", grid(charts['cohorts'], charts['rfm'] + charts['clv']), card(charts['repeat_cat']))}
{sec("cx", "Delivery performance and customer experience", f"Median delivery is {dlv['median_delivery_days']:.1f} days against a {dlv['avg_promised_days']:.0f}-day promise, so most orders arrive early - and still {dlv['late_rate']:.1%} miss the date, peaking at {dlv['worst_late_month_rate']:.0%} in {dlv['worst_late_month']} (carrier capacity, then the May-2018 truckers' strike). Late orders lose time in transit (median {dlv['median_transit_days_late']:.0f} vs {dlv['median_transit_days_on_time']:.0f} days), not at the seller. Controlling for order value, distance and basket size, lateness dominates every other driver of bad reviews; multi-seller baskets are the second-largest driver ({dlv['odds_ratio_multi_seller']:.1f}x odds).", grid(charts['delivery_reviews'], charts['late_monthly']), grid(charts['odds'], charts['delivery_state']))}
{sec("sellers", "Seller economics", f"{sel['active_sellers']:,} sellers sold in the window; the median seller made R${sel['median_seller_gmv']:,.0f} and {sel['sellers_single_order_share']:.0%} sold exactly once. A composite health score (50% volume, 25% on-time rate, 25% reviews) tiers sellers A-D; {sel['problem_sellers']} sellers with 50+ orders combine a >=12% late rate with reviews <=3.8 and account for R${sel['problem_sellers_gmv'] / 1e3:,.0f}K of GMV - the enforcement list. Seller churn mirrors customer churn: {sel['seller_active_m1']:.0%} of a cohort sells again the next month and {sel['seller_active_m6']:.0%} six months later.", grid(charts['pareto'], charts['tiers']), card(charts['seller_activity']))}
{sec("funnel", "Seller acquisition funnel (B2B marketing)", f"{fun['mqls']:,} marketing-qualified leads became {fun['deals']} closed deals ({fun['close_rate']:.1%}) in a median {fun['median_days_to_close']:.0f} days, and {fun['activated']} of those sellers ({fun['activation_rate']:.0%}) made at least one sale, a median {fun['median_days_won_to_first_sale']:.0f} days after signing. Measured on GMV per lead rather than close rate, paid search (R${fun['paid_search_gmv_per_mql']:,.0f}) and organic search (R${fun['organic_gmv_per_mql']:,.0f}) outperform social (R${fun['social_gmv_per_mql']:,.0f}, close rate {fun['social_close_rate']:.1%}) by ~3x. Value is concentrated: the top 5 activated sellers produced {fun['top5_activated_sellers_gmv_share']:.0%} of all funnel GMV. {fun['unknown_origin_share']:.0%} of leads have no recorded source - a tracking gap worth closing before re-allocating budget.", grid(charts['funnel'], charts['channel']), card(charts['segment']))}
{sec("geo", "Geography", f"Sao Paulo state is {geo['sp_gmv_share']:.0%} of GMV and {geo['orders_from_sp_sellers_share']:.0%} of orders ship from SP sellers; {geo['interstate_order_share']:.0%} of orders cross a state line. The North region is {geo['north_gmv_share']:.1%} of GMV but waits {geo['north_delivery_days']:.0f} days on average and pays freight worth {geo['north_freight_ratio']:.0%} of the product price (SP: {geo['sp_delivery_days']:.0f} days, {geo['sp_freight_ratio']:.0%}). The Northeast has the highest late rate at {geo['northeast_late_rate']:.0%}.", grid(charts['map'], charts['state']))}
{sec("forecast", "Weekly GMV forecast", f"Three models were compared on a {fc['folds']}-fold rolling-origin backtest with an {fc['horizon_weeks']}-week horizon. The '{fc['best_model']}' baseline won (mean WAPE {fc['backtest_wape'][fc['best_model']]:.1%}); Holt-Winters damped trend was close ({fc['backtest_wape'].get('holt_damped', float('nan')):.1%}) and log-SARIMA over-forecast ({fc['backtest_bias'].get('sarima_log', float('nan')):+.0%} bias) because it extrapolated 2017 growth into the 2018 plateau. Honest takeaway: with 85 weeks of history and a regime change, a well-chosen naive baseline is hard to beat; the value of the exercise is the backtest harness, not the point forecast. Next 8 weeks: ~{_money(fc['next_8w_gmv_best'])}.", card(charts['forecast']))}
{sec("models", "Predictive models", f"<b>Late-delivery risk (operational):</b> gradient boosting on checkout-time features with point-in-time seller history, trained to Feb-2018 and tested forward on Mar-Jul 2018: AUC {risk['gbm_auc']:.2f}, PR-AUC {risk['gbm_pr_auc']:.2f} vs a {risk['test_late_rate']:.1%} base rate. The riskiest decile is late {risk['top_decile_late_rate']:.0%} of the time ({risk['top_decile_lift']:.1f}x) and the top two deciles capture {risk['top2_decile_capture']:.0%} of all late orders - enough to drive proactive customer notification. <b>Repeat-purchase propensity (strategic):</b> deliberately reported as a weak result - AUC {prop['champion_auc']:.2f}. First-order attributes barely predict who comes back, which says the retention problem is structural (assortment, one-off purchases) rather than a targeting problem.", grid(charts['risk_lift'], charts['risk_imp']), grid(charts['risk_cal'], charts['prop_lift']))}
<section id="recs"><h2>Recommendations and how to test them</h2>
<ol class="recs">
<li><b>Proactive delay management.</b> Score every order at checkout with the risk model; for the top 20% risk, pad the promised date and send a proactive ETA update with a small voucher when the carrier scan slips. Target: cut 1-2 star reviews among flagged orders by 25%.</li>
<li><b>Seller SLA and tiering.</b> Publish the A-D health score to sellers; require &lt;=2-day handling for C/D tiers and route the {sel['problem_sellers']} problem sellers to a remediation plan or delisting.</li>
<li><b>Re-allocate B2B acquisition spend from social to search</b> on a GMV-per-lead basis, and fix source tracking on the {fun['unknown_origin_share']:.0%} of leads with unknown origin first.</li>
<li><b>Win-back the {seg['segments']['Lapsed High-Value']['customers']:,} lapsed high-value customers</b> with a holdout-measured voucher campaign; stop paying to re-acquire the Hibernating segment ({seg['hibernating_customer_share']:.0%} of customers, {seg['segments']['Hibernating']['gmv_share']:.0%} of GMV).</li>
<li><b>Reduce multi-seller baskets' failure rate</b> (second-largest review driver) by consolidating shipments or surfacing per-seller ETAs at checkout.</li>
</ol>
<p class="intro">Each recommendation maps to a pre-registered experiment. Sample sizes below use the 2018 run-rate of {exp['orders_per_week_2018']:,.0f} orders/week.</p>
{exp_table}
</section>
</main>
<script>
// Plotly sizes each chart when its own <script> runs, before later grid cards exist; re-fit once the page is laid out.
function fitCharts(){{document.querySelectorAll('.plotly-graph-div').forEach(function(g){{try{{Plotly.Plots.resize(g)}}catch(e){{}}}})}}
window.addEventListener('load',function(){{fitCharts();setTimeout(fitCharts,300)}});
if(window.ResizeObserver){{var ro=new ResizeObserver(function(){{fitCharts()}});document.querySelectorAll('.card').forEach(function(c){{ro.observe(c)}})}}
</script>
<footer>Data: Olist Brazilian E-Commerce Public Dataset + Marketing Funnel dataset (Kaggle, CC BY-NC-SA 4.0). Built with dbt-duckdb, pandas, scikit-learn, statsmodels, lifetimes, Plotly. All figures reproducible with <code>make all</code>.</footer>
</body></html>"""
    out = REPORTS_DIR / "dashboard.html"
    out.write_text(html)
    pages = ROOT / "docs" / "index.html"
    pages.parent.mkdir(exist_ok=True)
    pages.write_text(html)
    return out
