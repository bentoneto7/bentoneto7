import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st
import plotly.express as px

from core import database, analyzer, auth
from core.page_guard import require_login

database.init_db()

st.set_page_config(page_title="Tendências | Content Radar", page_icon="📡", layout="wide")
require_login()

st.title("📈 Tendências de Conteúdo")
st.caption("Análise de tendências dos perfis monitorados")

# Sidebar filters
with st.sidebar:
    session_user = auth.get_session_username()
    if session_user:
        st.markdown(f"Logado como **@{session_user}**")
        if st.button("Sair", use_container_width=True, key="logout_trends"):
            auth.logout()
            st.session_state.logged_in = False
            st.rerun()
        st.divider()
    st.subheader("Filtros")
    days = st.slider("Período (dias)", 7, 90, 30)

    accounts = database.get_accounts()
    account_names = [a["username"] for a in accounts]
    selected_accounts = st.multiselect("Perfis", account_names, default=account_names)

account_filter = selected_accounts[0] if len(selected_accounts) == 1 else None

st.divider()

if not accounts:
    st.info("Adicione perfis na página **Contas** e execute um scrape primeiro.")
    st.stop()

post_count = database.get_post_count()
if post_count == 0:
    st.info("Nenhum post coletado ainda. Vá para a página **Contas** e clique em **Coletar**.")
    st.stop()

# Top Hashtags + Post Type Distribution
col_hash, col_type = st.columns(2)

with col_hash:
    st.subheader("🏷️ Hashtags Mais Usadas")
    hashtags_df = analyzer.get_top_hashtags(days=days, limit=20, account_username=account_filter)
    if not hashtags_df.empty:
        fig = px.bar(
            hashtags_df, x="count", y="hashtag", orientation="h",
            labels={"count": "Frequência", "hashtag": ""},
            color="count", color_continuous_scale="Teal",
        )
        fig.update_layout(
            height=500, margin=dict(l=0, r=0, t=10, b=0),
            yaxis=dict(autorange="reversed"), showlegend=False,
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados de hashtags para o período selecionado.")

with col_type:
    st.subheader("📊 Distribuição de Tipos de Post")
    type_df = analyzer.get_post_type_distribution(days=days, account_username=account_filter)
    if not type_df.empty:
        type_labels = {"image": "Imagem", "video": "Vídeo", "carousel": "Carrossel"}
        type_df["tipo"] = type_df["post_type"].map(lambda x: type_labels.get(x, x))

        fig = px.pie(
            type_df, values="count", names="tipo",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados de tipos de post.")

st.divider()

# Keywords
st.subheader("💬 Palavras-chave Mais Comuns nas Captions")
keywords_df = analyzer.get_caption_keywords(days=days, limit=30, account_username=account_filter)
if not keywords_df.empty:
    fig = px.bar(
        keywords_df.head(20), x="keyword", y="count",
        labels={"keyword": "Palavra", "count": "Frequência"},
        color="count", color_continuous_scale="Viridis",
    )
    fig.update_layout(
        height=350, margin=dict(l=0, r=0, t=10, b=0),
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Sem dados de captions.")

st.divider()

# Posting patterns heatmap
st.subheader("🕐 Padrões de Horário de Postagem")
patterns_df = analyzer.get_posting_patterns(days=days, account_username=account_filter)
if not patterns_df.empty:
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_labels = {
        "Monday": "Segunda", "Tuesday": "Terça", "Wednesday": "Quarta",
        "Thursday": "Quinta", "Friday": "Sexta", "Saturday": "Sábado", "Sunday": "Domingo",
    }
    patterns_df["dia"] = patterns_df["day_of_week"].map(day_labels)

    # Pivot for heatmap
    pivot = patterns_df.pivot_table(index="dia", columns="hour", values="count", fill_value=0)

    # Reorder days
    ordered_days = [day_labels[d] for d in day_order if day_labels[d] in pivot.index]
    if ordered_days:
        pivot = pivot.reindex(ordered_days)

        fig = px.imshow(
            pivot,
            labels=dict(x="Hora do Dia", y="Dia da Semana", color="Posts"),
            color_continuous_scale="YlOrRd",
            aspect="auto",
        )
        fig.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados suficientes para análise de horários.")
else:
    st.info("Sem dados suficientes para análise de horários.")
