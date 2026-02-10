import streamlit as st

from core import database, ai_generator

database.init_db()

st.set_page_config(page_title="Ideias | Content Radar", page_icon="📡", layout="wide")

st.title("💡 Gerador de Ideias com IA")
st.caption("Gere ideias criativas de conteúdo baseadas nas tendências dos perfis monitorados")

st.divider()

accounts = database.get_accounts()
account_names = [a["username"] for a in accounts]

if not accounts:
    st.info("Adicione perfis na página **Contas** e execute um scrape primeiro.")
    st.stop()

# Generation controls
tab_generate, tab_history = st.tabs(["🆕 Gerar Ideias", "📚 Histórico"])

with tab_generate:
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        selected_accounts = st.multiselect(
            "Baseado nos perfis:",
            account_names,
            default=account_names,
        )

    with col2:
        theme = st.text_input(
            "Foco temático (opcional):",
            placeholder="Ex: dicas de produtividade, receitas rápidas...",
        )

    with col3:
        num_ideas = st.slider("Quantidade:", 3, 10, 5)

    if st.button("🚀 Gerar Ideias", use_container_width=True, type="primary"):
        if not selected_accounts:
            st.warning("Selecione pelo menos um perfil.")
        else:
            with st.spinner("🧠 Gerando ideias criativas com IA..."):
                try:
                    ideas = ai_generator.generate_content_ideas(
                        accounts=selected_accounts,
                        theme=theme,
                        num_ideas=num_ideas,
                    )

                    # Save to database
                    database.save_ideas(ideas, based_on_accounts=selected_accounts)

                    st.success(f"✅ {len(ideas)} ideias geradas!")

                    # Display ideas
                    for i, idea in enumerate(ideas, 1):
                        format_icons = {
                            "image": "🖼️", "video": "🎬",
                            "carousel": "🎠", "reel": "🎞️",
                        }
                        fmt = idea.get("suggested_format", "image")
                        icon = format_icons.get(fmt, "📝")

                        with st.container():
                            st.markdown(f"### {icon} {i}. {idea.get('title', 'Sem título')}")
                            st.markdown(idea.get("description", ""))

                            tag_col, fmt_col = st.columns([3, 1])
                            with tag_col:
                                hashtags = idea.get("suggested_hashtags", [])
                                if hashtags:
                                    st.markdown("**Hashtags:** " + " ".join(f"`#{h.lstrip('#')}`" for h in hashtags))
                            with fmt_col:
                                st.markdown(f"**Formato:** {fmt.capitalize()}")

                            with st.expander("🤔 Por que essa ideia?"):
                                st.markdown(idea.get("reasoning", "Sem explicação disponível."))

                            st.divider()

                except Exception as e:
                    st.error(f"Erro ao gerar ideias: {e}")
                    st.caption("Verifique se a chave ANTHROPIC_API_KEY está configurada no arquivo .env")

with tab_history:
    ideas = database.get_ideas()

    if not ideas:
        st.info("Nenhuma ideia gerada ainda. Use a aba **Gerar Ideias** para começar.")
    else:
        # Filter
        show_saved = st.checkbox("Mostrar apenas salvos", value=False)
        if show_saved:
            ideas = [i for i in ideas if i["is_saved"]]

        for idea in ideas:
            format_icons = {
                "image": "🖼️", "video": "🎬",
                "carousel": "🎠", "reel": "🎞️",
            }
            fmt = idea.get("suggested_format", "image")
            icon = format_icons.get(fmt, "📝")
            saved_mark = "⭐ " if idea["is_saved"] else ""

            with st.container():
                h_col, s_col = st.columns([4, 1])

                with h_col:
                    st.markdown(f"#### {saved_mark}{icon} {idea['title']}")
                    st.caption(f"Criado em: {idea['created_at'][:16].replace('T', ' ')} | "
                             f"Baseado em: {', '.join(idea['based_on_accounts'])}")
                    st.markdown(idea.get("description", ""))

                    hashtags = idea.get("suggested_hashtags", [])
                    if hashtags:
                        st.markdown(" ".join(f"`#{h.lstrip('#')}`" for h in hashtags))

                with s_col:
                    label = "⭐ Salvo" if idea["is_saved"] else "☆ Salvar"
                    if st.button(label, key=f"save_{idea['id']}"):
                        database.toggle_idea_saved(idea["id"])
                        st.rerun()

                with st.expander("Ver raciocínio"):
                    st.markdown(idea.get("reasoning", ""))

                st.divider()
