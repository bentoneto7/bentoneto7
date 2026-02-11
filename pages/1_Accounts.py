import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st

from core import database, scraper, auth
from core.page_guard import require_login

database.init_db()

st.set_page_config(page_title="Contas | Content Radar", page_icon="📡", layout="wide")
require_login()

# Sidebar: session info
with st.sidebar:
    session_user = auth.get_session_username()
    if session_user:
        st.markdown(f"Logado como **@{session_user}**")
        if st.button("Sair", use_container_width=True, key="logout_accounts"):
            auth.logout()
            st.session_state.logged_in = False
            st.rerun()
        st.divider()

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
        if not username:
            st.warning("Digite um username válido.")
        elif database.add_account(username):
            st.success(f"@{username} adicionado!")
            st.rerun()
        else:
            st.warning(f"@{username} já está na lista.")

st.divider()

# Scrape all button
accounts = database.get_accounts()

if accounts:
    col_scrape, col_count = st.columns([1, 3])
    with col_scrape:
        if st.button("Coletar Todos", use_container_width=True):
            import time as _time

            progress = st.progress(0, text="Iniciando coleta...")
            status_text = st.empty()
            results = []
            total_start = _time.time()
            max_total_time = 120  # 2 min total max

            for i, account in enumerate(accounts):
                if _time.time() - total_start > max_total_time:
                    status_text.warning(
                        f"Tempo total excedido (2 min). Coletados {i}/{len(accounts)} perfis."
                    )
                    break

                progress.progress(
                    (i) / len(accounts),
                    text=f"Coletando @{account['username']}... ({i+1}/{len(accounts)})",
                )
                status_text.info(f"Coletando @{account['username']}... (limite: 45s por perfil)")

                result = scraper.scrape_account(account["username"])
                result["username"] = account["username"]
                results.append(result)

                # If session expired, stop and notify
                if not result["success"] and result.get("error", ""):
                    err = result["error"].lower()
                    if "sessão expirada" in err or "login" in err:
                        progress.progress(1.0, text="Coleta interrompida")
                        status_text.empty()
                        st.error("Sessão expirada. Faça logout e login novamente na página principal.")
                        break

            progress.progress(1.0, text="Coleta finalizada!")
            status_text.empty()

            success_count = sum(1 for r in results if r["success"])
            total_posts = sum(r["posts_scraped"] for r in results)
            st.success(f"{success_count}/{len(accounts)} perfis coletados — {total_posts} posts no total")

            for r in results:
                if not r["success"]:
                    st.warning(f"@{r['username']}: {r['error']}")
                elif r.get("error"):
                    st.info(f"@{r['username']}: {r['error']}")

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
                private = " 🔒" if account.get("is_private") else ""
                st.markdown(f"**@{account['username']}**{private}")
                if name:
                    st.caption(name)

            with c2:
                followers = account.get("followers") or 0
                if followers:
                    if followers >= 1_000_000:
                        display = f"{followers/1_000_000:.1f}M"
                    elif followers >= 1_000:
                        display = f"{followers/1_000:.1f}K"
                    else:
                        display = str(followers)
                    st.metric("Seguidores", display)
                else:
                    st.metric("Seguidores", "—")

            with c3:
                last = account.get("last_scraped_at")
                if last:
                    st.caption(f"Último scrape:\n{last[:16].replace('T', ' ')}")
                else:
                    st.caption("Nunca coletado")

            with c4:
                if st.button("Coletar", key=f"scrape_{account['username']}"):
                    status = st.empty()
                    status.info(f"Coletando @{account['username']}... (limite: 45s)")
                    result = scraper.scrape_account(account["username"])
                    status.empty()
                    if result["success"]:
                        msg = f"{result['posts_scraped']} posts coletados"
                        if result.get("error"):
                            msg += f" (aviso: {result['error']})"
                        st.success(msg)
                    else:
                        st.error(f"Erro: {result['error']}")
                    st.rerun()

            with c5:
                if st.button("🗑️", key=f"remove_{account['username']}"):
                    database.remove_account(account["username"])
                    st.rerun()

            st.divider()
else:
    st.info("Nenhuma conta monitorada. Adicione um @username acima para começar.")
