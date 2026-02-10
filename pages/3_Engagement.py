import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st
import plotly.express as px

from core import database, analyzer

database.init_db()

st.set_page_config(page_title="Engajamento | Content Radar", page_icon="📡", layout="wide")

st.title("❤️ Métricas de Engajamento")
st.caption("Análise detalhada de engajamento dos perfis monitorados")

# Sidebar filters
with st.sidebar:
    st.subheader("Filtros")
    days = st.slider("Período (dias)", 7, 90, 30)

    accounts = database.get_accounts()
    account_names = [a["username"] for a in accounts]
    selected_accounts = st.multiselect("Perfis", account_names, default=account_names)

    post_types = st.multiselect(
        "Tipo de Post",
        ["image", "video", "carousel"],
        default=["image", "video", "carousel"],
    )

st.divider()

if not accounts:
    st.info("Adicione perfis na página **Contas** e execute um scrape primeiro.")
    st.stop()

post_count = database.get_post_count()
if post_count == 0:
    st.info("Nenhum post coletado ainda. Vá para a página **Contas** e clique em **Coletar**.")
    st.stop()

# Per-account comparison
st.subheader("📊 Comparação por Conta")
summary = analyzer.get_engagement_summary(days=days)
if not summary.empty:
    if selected_accounts:
        summary = summary[summary["account_username"].isin(selected_accounts)]

    if not summary.empty:
        col1, col2 = st.columns(2)

        with col1:
            fig = px.bar(
                summary, x="account_username", y="avg_likes",
                labels={"account_username": "Perfil", "avg_likes": "Média de Likes"},
                color="avg_likes", color_continuous_scale="Blues",
            )
            fig.update_layout(
                height=350, margin=dict(l=0, r=0, t=30, b=0),
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.bar(
                summary, x="account_username", y="avg_engagement_rate",
                labels={"account_username": "Perfil", "avg_engagement_rate": "Taxa de Engajamento"},
                color="avg_engagement_rate", color_continuous_scale="Oranges",
            )
            fig.update_layout(
                height=350, margin=dict(l=0, r=0, t=30, b=0),
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True)

st.divider()

# Engagement by post type
st.subheader("📈 Engajamento por Tipo de Post")
df = analyzer.get_posts_dataframe(days=days)
if not df.empty:
    if selected_accounts:
        df = df[df["account_username"].isin(selected_accounts)]
    if post_types:
        df = df[df["post_type"].isin(post_types)]

    if not df.empty:
        type_labels = {"image": "Imagem", "video": "Vídeo", "carousel": "Carrossel"}
        df = df.copy()
        df["tipo"] = df["post_type"].map(lambda x: type_labels.get(x, x))

        fig = px.box(
            df, x="tipo", y="engagement_rate",
            labels={"tipo": "Tipo de Post", "engagement_rate": "Taxa de Engajamento"},
            color="tipo",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# Top performing posts
st.subheader("🏆 Top Posts por Engajamento")
account_filter = selected_accounts[0] if len(selected_accounts) == 1 else None
top_posts = analyzer.get_top_posts(days=days, limit=10, account_username=account_filter)

if not top_posts.empty:
    if selected_accounts and len(selected_accounts) > 1:
        top_posts = top_posts[top_posts["account_username"].isin(selected_accounts)]

    for _, post in top_posts.iterrows():
        likes = int(post["likes"])
        comments = int(post["comments"])
        with st.expander(
            f"@{post['account_username']} — ❤️ {likes:,} 💬 {comments:,} "
            f"| Engajamento: {post['engagement_rate']:.2%}"
        ):
            post_type_label = {"image": "Imagem", "video": "Vídeo", "carousel": "Carrossel"}.get(
                post["post_type"], post["post_type"]
            )
            st.markdown(f"**Tipo:** {post_type_label} | **Data:** {str(post['posted_at'])[:10]}")
            caption_text = str(post["caption"] or "Sem caption")
            st.markdown(f"**Caption:**\n{caption_text[:500]}")
            url = post.get("url") or ""
            if url:
                st.markdown(f"[Ver no Instagram]({url})")

st.divider()

# Full posts table
st.subheader("📋 Todos os Posts")
all_df = analyzer.get_posts_dataframe(days=days)
if not all_df.empty:
    if selected_accounts:
        all_df = all_df[all_df["account_username"].isin(selected_accounts)]
    if post_types:
        all_df = all_df[all_df["post_type"].isin(post_types)]

    if not all_df.empty:
        display_df = all_df[["account_username", "post_type", "likes", "comments",
                             "engagement_rate", "posted_at"]].copy()
        display_df.columns = ["Perfil", "Tipo", "Likes", "Comentários", "Engajamento", "Data"]
        display_df = display_df.sort_values("Engajamento", ascending=False)

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Engajamento": st.column_config.NumberColumn(format="%.4f"),
                "Likes": st.column_config.NumberColumn(format="%d"),
                "Comentários": st.column_config.NumberColumn(format="%d"),
            },
        )
    else:
        st.info("Sem dados para os filtros selecionados.")
else:
    st.info("Sem dados para o período selecionado.")
