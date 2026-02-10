import streamlit as st

from core import database, scraper

database.init_db()

st.set_page_config(page_title="Contas | Content Radar", page_icon="📡", layout="wide")

st.title("👥 Contas Monitoradas")
st.caption("Gerencie os perfis do Instagram que você quer monitorar")

st.divider()

# Add account form
with st.form("add_account", clear_on_submit=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        new_username = st.text_input(
            "Adicionar perfil",
            placeholder="@username ou username",
            label_visibility="collapsed",
        )
    with col2:
        submitted = st.form_submit_button("➕ Adicionar", use_container_width=True)

    if submitted and new_username:
        username = new_username.strip().lstrip("@")
        if database.add_account(username):
            st.success(f"✅ @{username} adicionado!")
            st.rerun()
        else:
            st.warning(f"@{username} já está na lista.")

st.divider()

# Scrape all button
accounts = database.get_accounts()

if accounts:
    col_scrape, col_count = st.columns([1, 3])
    with col_scrape:
        if st.button("🔄 Coletar Todos", use_container_width=True):
            with st.spinner("Coletando dados de todos os perfis..."):
                results = scraper.scrape_all_accounts()
                for r in results:
                    if r["success"]:
                        st.toast(f"✅ @{r['username']}: {r['posts_scraped']} posts")
                    else:
                        st.toast(f"❌ @{r['username']}: {r['error']}")
                st.rerun()
    with col_count:
        st.caption(f"{len(accounts)} perfis monitorados")

    st.divider()

    # Account list
    for account in accounts:
        with st.container():
            c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])

            with c1:
                name = account.get("full_name") or ""
                st.markdown(f"**@{account['username']}**")
                if name:
                    st.caption(name)

            with c2:
                followers = account.get("followers") or 0
                st.metric("Seguidores", f"{followers:,}" if followers else "—")

            with c3:
                last = account.get("last_scraped_at")
                if last:
                    st.caption(f"Último scrape:\n{last[:16].replace('T', ' ')}")
                else:
                    st.caption("Nunca coletado")

            with c4:
                if st.button("🔄 Coletar", key=f"scrape_{account['username']}"):
                    with st.spinner(f"Coletando @{account['username']}..."):
                        result = scraper.scrape_account(account["username"])
                        if result["success"]:
                            st.success(f"{result['posts_scraped']} posts coletados")
                        else:
                            st.error(result["error"])
                        st.rerun()

            with c5:
                if st.button("🗑️", key=f"remove_{account['username']}"):
                    database.remove_account(account["username"])
                    st.rerun()

            st.divider()
else:
    st.info("Nenhuma conta monitorada. Adicione um @username acima para começar.")
