import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

import config
from core import database, auth, meta_ads, ai_generator
from core.page_guard import require_login

database.init_db()

st.set_page_config(
    page_title="Relatório | Content Radar",
    page_icon="📡",
    layout="wide",
)
require_login()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    session_user = auth.get_session_username()
    if session_user:
        st.markdown(f"Logado como **@{session_user}**")
        if st.button("Sair", use_container_width=True, key="logout_rel"):
            auth.logout()
            st.session_state.logged_in = False
            st.rerun()
        st.divider()

    st.markdown("### 📅 Período")
    date_preset = st.selectbox(
        "Janela de análise:",
        ["today", "yesterday", "last_7_d", "last_14_d", "last_30_d", "this_month"],
        format_func=lambda x: {
            "today":       "Hoje",
            "yesterday":   "Ontem",
            "last_7_d":    "Últimos 7 dias",
            "last_14_d":   "Últimos 14 dias",
            "last_30_d":   "Últimos 30 dias",
            "this_month":  "Este mês",
        }[x],
        index=2,
    )

    if "product_price" not in st.session_state:
        st.session_state["product_price"] = float(database.get_config("product_price", "0"))
    product_price = st.session_state["product_price"]
    if product_price > 0:
        st.caption(f"Produto: R$ {product_price:.2f}")

    st.divider()
    refresh = st.button("🔄 Atualizar dados", use_container_width=True)
    if refresh:
        st.cache_data.clear()
        st.rerun()

# ── Credential check ──────────────────────────────────────────────────────────
if not config.META_ACCESS_TOKEN or not config.META_AD_ACCOUNT_ID:
    st.warning("Configure as credenciais Meta Ads no arquivo `.env`.")
    st.stop()

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=120, show_spinner=False)
def load_daily(preset):
    return meta_ads.get_account_daily_insights(preset)

@st.cache_data(ttl=120, show_spinner=False)
def load_campaigns(preset):
    return meta_ads.get_campaigns_performance(preset)

@st.cache_data(ttl=120, show_spinner=False)
def load_top_ads(preset):
    return meta_ads.get_top_ads(limit=10, date_preset=preset)

try:
    with st.spinner("Carregando dados da conta..."):
        daily_data  = load_daily(date_preset)
        campaigns   = load_campaigns(date_preset)
        top_ads     = load_top_ads(date_preset)
except Exception as e:
    st.error(f"Erro ao conectar com a Meta API: {e}")
    st.stop()

# ── Aggregate totals ──────────────────────────────────────────────────────────
def agg(daily, key):
    return sum(r.get(key, 0) for r in daily)

def avg(daily, key):
    vals = [r.get(key, 0) for r in daily if r.get(key, 0) > 0]
    return sum(vals) / len(vals) if vals else 0

total_spend       = agg(daily_data, "spend")
total_impressions = agg(daily_data, "impressions")
total_clicks      = agg(daily_data, "clicks")
total_reach       = agg(daily_data, "reach")
total_conversions = agg(daily_data, "conversions")
total_conv_value  = agg(daily_data, "conversion_value")
avg_ctr           = avg(daily_data, "ctr")
avg_cpc           = avg(daily_data, "cpc")
avg_cpm           = avg(daily_data, "cpm")
avg_freq          = avg(daily_data, "frequency")
cpa               = total_spend / total_conversions if total_conversions > 0 else 0
roas              = total_conv_value / total_spend if total_spend > 0 else 0
avg_daily_spend   = total_spend / len(daily_data) if daily_data else 0

totals = {
    "spend": total_spend, "impressions": total_impressions,
    "clicks": total_clicks, "reach": total_reach,
    "conversions": total_conversions, "conversion_value": total_conv_value,
    "ctr": avg_ctr, "cpc": avg_cpc, "cpm": avg_cpm,
    "frequency": avg_freq, "cpa": cpa, "roas": roas,
}

# ── Helper: sparkline bar chart ───────────────────────────────────────────────
def sparkline(daily, key, color="#4A90D9", fmt=None):
    if not daily:
        return go.Figure()
    dates = [r["date"][5:] for r in daily]   # MM-DD
    values = [r.get(key, 0) for r in daily]
    fig = go.Figure(go.Bar(
        x=dates, y=values,
        marker_color=color,
        hovertemplate="%{x}: %{y:.2f}<extra></extra>" if fmt == "float"
                 else "%{x}: %{y:,}<extra></extra>",
    ))
    fig.update_layout(
        height=80, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig

# ── Helper: delta label ───────────────────────────────────────────────────────
def delta_html(value, label, positive_is_good=True, prefix="", suffix="", fmt=".2f"):
    color = "#28a745" if positive_is_good else "#dc3545"
    return (
        f'<div style="font-size:0.75rem;color:#aaa;margin-bottom:2px">{label}</div>'
        f'<div style="font-size:1.6rem;font-weight:700;color:#fff">'
        f'{prefix}{value:{fmt}}{suffix}</div>'
    )

# ── Title ─────────────────────────────────────────────────────────────────────
st.title("📊 Relatório de Performance")
period_label = {
    "today": "Hoje", "yesterday": "Ontem",
    "last_7_d": "Últimos 7 dias", "last_14_d": "Últimos 14 dias",
    "last_30_d": "Últimos 30 dias", "this_month": "Este mês",
}.get(date_preset, date_preset)
st.caption(f"Período: **{period_label}** · Conta: `{config.META_AD_ACCOUNT_ID}`")
st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# 1. FUNIL DE PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Performance de funil")

funnel_fig = go.Figure(go.Funnel(
    y=["Impressões", "Cliques", "Conversões"],
    x=[total_impressions, total_clicks, total_conversions],
    textposition="inside",
    textinfo="value+percent initial",
    marker=dict(color=["#2196F3", "#42A5F5", "#90CAF9"]),
    connector=dict(line=dict(color="#555", width=1)),
))
funnel_fig.update_layout(
    height=220,
    margin=dict(l=0, r=0, t=10, b=0),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#fff"),
)

col_funnel, col_invest = st.columns([3, 1])

with col_funnel:
    st.plotly_chart(funnel_fig, use_container_width=True)

    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Impressões", f"{total_impressions:,}", help="Total de veiculações")
    f2.metric("Cliques", f"{total_clicks:,}",
              delta=f"CTR {avg_ctr:.2f}%",
              delta_color="normal")
    f3.metric("Conversões", f"{total_conversions:,}",
              delta=f"{total_conversions/total_clicks*100:.1f}% dos cliques" if total_clicks > 0 else None)
    f4.metric("CPA", f"R$ {cpa:.2f}" if cpa else "—",
              delta="Sem pixel" if total_conversions == 0 else None,
              delta_color="off")

with col_invest:
    with st.container(border=True):
        st.markdown("**Valor Investido**")
        st.markdown(f"## R$ {total_spend:,.2f}")
        if daily_data:
            st.plotly_chart(sparkline(daily_data, "spend", "#f44336"), use_container_width=True)

    with st.container(border=True):
        st.markdown("**Investimento médio diário**")
        st.markdown(f"## R$ {avg_daily_spend:,.2f}")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# 2. GRADE DE MÉTRICAS COM SPARKLINES
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Métricas do período")

metrics_row1 = [
    ("Alcance",     total_reach,       "reach",     "#4A90D9", ",d",    False),
    ("Impressões",  total_impressions,  "impressions","#5B9BD5", ",d",  False),
    ("CTR",         avg_ctr,           "ctr",        "#42A5F5", ".2f%", True),
    ("Cliques",     total_clicks,      "clicks",     "#64B5F6", ",d",   False),
]
metrics_row2 = [
    ("CPC (R$)",   avg_cpc,   "cpc",       "#FF7043", ".2f",  True),
    ("CPM (R$)",   avg_cpm,   "cpm",       "#FFA726", ".2f",  True),
    ("Frequência", avg_freq,  "frequency", "#AB47BC", ".2f",  True),
]

def metric_card(label, value, spark_key, color, fmt, lower_is_better):
    with st.container(border=True):
        if "%" in fmt:
            display = f"{value:.2f}%"
        elif "d" in fmt:
            display = f"{value:,.0f}"
        else:
            display = f"R$ {value:.2f}" if "CPC" in label or "CPM" in label or "R$" in label else f"{value:.2f}"
        st.markdown(f"**{label}**")
        st.markdown(f"### {display}")
        if daily_data:
            st.plotly_chart(
                sparkline(daily_data, spark_key, color),
                use_container_width=True,
            )

cols1 = st.columns(4)
for col, (label, value, key, color, fmt, lib) in zip(cols1, metrics_row1):
    with col:
        metric_card(label, value, key, color, fmt, lib)

cols2 = st.columns(4)
for col, (label, value, key, color, fmt, lib) in zip(cols2, metrics_row2):
    with col:
        metric_card(label, value, key, color, fmt, lib)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# 3. RETORNO SOBRE INVESTIMENTO
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Retorno sobre investimento")

r1, r2, r3, r4 = st.columns(4)

with r1:
    with st.container(border=True):
        st.markdown("**CPA**")
        cpa_display = f"R$ {cpa:.2f}" if cpa > 0 else "—"
        if product_price > 0 and cpa > 0:
            pct = cpa / product_price * 100
            color = "green" if pct <= 30 else "orange" if pct <= 50 else "red"
            st.markdown(f"### :{color}[{cpa_display}]")
            st.caption(f"{pct:.0f}% do produto")
        else:
            st.markdown(f"### {cpa_display}")
        if daily_data:
            daily_cpa = [
                {"date": r["date"],
                 "cpa": r["spend"] / r["conversions"] if r["conversions"] > 0 else 0}
                for r in daily_data
            ]
            fig = go.Figure(go.Bar(
                x=[r["date"][5:] for r in daily_cpa],
                y=[r["cpa"] for r in daily_cpa],
                marker_color="#FF7043",
            ))
            fig.update_layout(
                height=80, margin=dict(l=0,r=0,t=0,b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(visible=False), yaxis=dict(visible=False),
            )
            st.plotly_chart(fig, use_container_width=True)

with r2:
    with st.container(border=True):
        st.markdown("**Conversões**")
        st.markdown(f"### {total_conversions:,}")
        if daily_data:
            st.plotly_chart(
                sparkline(daily_data, "conversions", "#66BB6A"),
                use_container_width=True,
            )

with r3:
    with st.container(border=True):
        st.markdown("**Valor em conversões**")
        st.markdown(f"### R$ {total_conv_value:,.2f}")
        if daily_data:
            st.plotly_chart(
                sparkline(daily_data, "conversion_value", "#26A69A"),
                use_container_width=True,
            )

with r4:
    with st.container(border=True):
        st.markdown("**ROAS**")
        if roas > 0:
            color = "green" if roas >= 3 else "orange" if roas >= 1.5 else "red"
            st.markdown(f"### :{color}[{roas:.2f}x]")
        else:
            st.markdown("### —")
        if roas >= 3:
            st.caption("🟢 Lucrativo")
        elif roas >= 1.5:
            st.caption("🟡 Marginal")
        elif roas > 0:
            st.caption("🔴 Abaixo do ponto de equilíbrio")
        else:
            st.caption("Pixel não configurado")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# 4. RANKING DE CAMPANHAS
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Campanhas no período")

if campaigns:
    import pandas as pd

    STATUS_ICON = {"ACTIVE": "🟢", "PAUSED": "🔴", "ARCHIVED": "⚪"}

    camp_rows = []
    for c in campaigns:
        pct_label = ""
        if product_price > 0 and c["cpa"] > 0:
            pct = c["cpa"] / product_price * 100
            emoji = "🟢" if pct <= 30 else "🟡" if pct <= 50 else "🔴"
            pct_label = f"{emoji} {pct:.0f}%"

        camp_rows.append({
            "Status":       STATUS_ICON.get(c["status"], "⚪"),
            "Campanha":     c["name"],
            "Gasto (R$)":   round(c["spend"], 2),
            "Impressões":   c["impressions"],
            "Cliques":      c["clicks"],
            "CTR (%)":      round(c["ctr"], 2),
            "CPC (R$)":     round(c["cpc"], 2),
            "Conversões":   c["conversions"],
            "CPA (R$)":     round(c["cpa"], 2),
            "ROAS":         round(c["roas"], 2),
            "% Produto":    pct_label,
        })

    df = pd.DataFrame(camp_rows)

    def highlight_roas(val):
        try:
            v = float(val)
            if v >= 3:    return "color: #28a745; font-weight:600"
            if v >= 1.5:  return "color: #ffc107; font-weight:600"
            if v > 0:     return "color: #dc3545; font-weight:600"
        except Exception:
            pass
        return ""

    def highlight_ctr(val):
        try:
            v = float(val)
            if v >= 2:   return "color: #28a745"
            if v >= 1:   return "color: #ffc107"
            return "color: #dc3545"
        except Exception:
            return ""

    styled = df.style.applymap(highlight_roas, subset=["ROAS"]) \
                     .applymap(highlight_ctr, subset=["CTR (%)"])

    st.dataframe(styled, use_container_width=True, hide_index=True)
else:
    st.info("Nenhuma campanha com dados no período.")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# 5. TOP CRIATIVOS
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Top criativos (por CTR)")

if top_ads:
    ad_rows = []
    for a in top_ads:
        ad_rows.append({
            "Criativo":    a["name"],
            "Impressões":  a["impressions"],
            "Cliques":     a["clicks"],
            "CTR (%)":     round(a["ctr"], 2),
            "CPC (R$)":    round(a["cpc"], 2),
            "Gasto (R$)":  round(a["spend"], 2),
            "Conversões":  a["conversions"],
        })
    st.dataframe(pd.DataFrame(ad_rows), use_container_width=True, hide_index=True)
else:
    st.info("Nenhum criativo com dados no período.")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# 6. DISCLAIMER IA — ANÁLISE CLAUDE
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("🤖 Diagnóstico com IA")

if not config.ANTHROPIC_API_KEY:
    st.warning("Configure `ANTHROPIC_API_KEY` no `.env` para ativar o diagnóstico com IA.")
else:
    cache_key = f"ai_report_{date_preset}_{total_spend:.0f}"

    if st.button("✨ Gerar análise", type="primary"):
        st.session_state[cache_key] = None

    if cache_key not in st.session_state or st.session_state.get(cache_key) is None:
        if st.session_state.get(f"run_ai_{cache_key}") or st.button(
            "Analisar automaticamente", key="auto_ai"
        ):
            with st.spinner("Claude analisando os dados..."):
                analysis = ai_generator.analyze_ads_performance(
                    totals=totals,
                    campaigns=campaigns,
                    top_ads=top_ads,
                    product_price=product_price,
                )
            st.session_state[cache_key] = analysis

    saved_analysis = st.session_state.get(cache_key)
    if saved_analysis:
        with st.container(border=True):
            st.markdown(saved_analysis)
