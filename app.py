import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stdout,
)

import streamlit as st
import plotly.express as px

import config
from core import database, analyzer, auth, scraper, ai_generator, loaders

# Initialize database
database.init_db()

# Restore session: try DB first, then env session, then auto-login with credentials
if not auth.is_logged_in():
    auth.restore_session_from_db()
if not auth.is_logged_in():
    auth.restore_session_from_env()
if not auth.is_logged_in():
    auth.auto_login_from_env()

st.set_page_config(
    page_title="Content Radar",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Session state init ───
if "logged_in" not in st.session_state:
    st.session_state.logged_in = auth.is_logged_in()
if "login_step" not in st.session_state:
    st.session_state.login_step = "credentials"  # "credentials", "2fa"
if "pending_username" not in st.session_state:
    st.session_state.pending_username = ""
if "pending_password" not in st.session_state:
    st.session_state.pending_password = ""
if "pending_remember" not in st.session_state:
    st.session_state.pending_remember = True
if "suggested_profiles" not in st.session_state:
    st.session_state.suggested_profiles = []
if "niche_analysis" not in st.session_state:
    st.session_state.niche_analysis = None
if "setup_done" not in st.session_state:
    st.session_state.setup_done = False


# ═══════════════════════════════════════════
# LOGIN SCREEN (SaaS-style)
# ═══════════════════════════════════════════

_LOGIN_CSS = """
<style>
/* Hide sidebar + header + footer on login */
[data-testid="stSidebar"],
[data-testid="stSidebarNav"],
header[data-testid="stHeader"],
#MainMenu, footer {
    display: none !important;
}

/* Full-height centered layout */
[data-testid="stAppViewContainer"] > .main {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
}

/* Login card */
.login-card {
    width: 100%;
    max-width: 420px;
    margin: 0 auto;
    padding: 2.5rem 2rem 2rem;
    background: #16181D;
    border: 1px solid #2A2D35;
    border-radius: 16px;
}

/* Brand header */
.login-brand {
    text-align: center;
    margin-bottom: 2rem;
}
.login-brand-icon {
    font-size: 2.8rem;
    line-height: 1;
    margin-bottom: 0.5rem;
}
.login-brand h1 {
    font-size: 1.6rem;
    font-weight: 700;
    margin: 0;
    color: #FAFAFA;
    letter-spacing: -0.5px;
}
.login-brand p {
    color: #6B7280;
    font-size: 0.9rem;
    margin: 0.3rem 0 0;
}

/* Divider */
.login-divider {
    border: none;
    border-top: 1px solid #2A2D35;
    margin: 1.5rem 0;
}

/* Footer text */
.login-footer {
    text-align: center;
    color: #4B5563;
    font-size: 0.78rem;
    line-height: 1.5;
    margin-top: 1.5rem;
}
.login-footer a {
    color: #6B7280;
    text-decoration: none;
}

/* 2FA badge */
.tfa-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.5rem 1rem;
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.25);
    border-radius: 8px;
    color: #A5B4FC;
    font-size: 0.85rem;
    margin-bottom: 1rem;
}

/* Security badge */
.security-badges {
    display: flex;
    justify-content: center;
    gap: 1.2rem;
    margin-top: 1rem;
}
.security-badge {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    color: #4B5563;
    font-size: 0.75rem;
}
</style>
"""


def show_login():
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    # Center the card using columns
    _, col_center, _ = st.columns([1, 2, 1])

    with col_center:
        st.markdown(
            '<div class="login-card">'
            '<div class="login-brand">'
            '<div class="login-brand-icon">📡</div>'
            "<h1>Content Radar</h1>"
            "<p>Monitore tendências e gere ideias para o Instagram</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        if st.session_state.login_step == "credentials":
            _show_credentials_form()
        elif st.session_state.login_step == "2fa":
            _show_2fa_form()

        st.markdown(
            '<hr class="login-divider">'
            '<div class="security-badges">'
            '<span class="security-badge">🔒 Conexão segura</span>'
            '<span class="security-badge">🍪 Só cookies de sessão</span>'
            '<span class="security-badge">🚫 Senha não armazenada</span>'
            "</div>"
            '<div class="login-footer">'
            "Suas credenciais autenticam diretamente com o Instagram.<br>"
            "Nenhuma senha é salva — apenas o cookie de sessão temporário."
            "</div>"
            "</div>",  # close login-card
            unsafe_allow_html=True,
        )


def _show_credentials_form():
    with st.form("login_form"):
        username = st.text_input(
            "Usuário do Instagram",
            placeholder="seu_usuario",
            help="Seu @ do Instagram (sem o @)",
        )
        password = st.text_input(
            "Senha",
            type="password",
            placeholder="Sua senha",
        )
        remember = st.checkbox(
            "Lembrar por 30 dias",
            value=True,
            help="Manter sessão ativa por 30 dias. Sem isso, expira em 24h.",
        )

        submitted = st.form_submit_button(
            "Entrar",
            use_container_width=True,
            type="primary",
        )

        if submitted:
            if not username or not password:
                st.error("Preencha usuário e senha.")
                return

            username = username.strip().lstrip("@")

            login_loader = st.empty()
            with login_loader.container():
                loaders.radar_loader("login")
            result = auth.login(username, password, remember=remember)
            login_loader.empty()

            if result["success"]:
                st.session_state.logged_in = True
                st.session_state.pending_username = username
                st.session_state.pending_password = ""
                st.session_state.setup_done = False
                st.success("Login realizado com sucesso!")
                st.rerun()
            elif result.get("needs_2fa"):
                st.session_state.login_step = "2fa"
                st.session_state.pending_username = username
                st.session_state.pending_password = password
                st.session_state.pending_remember = remember
                st.rerun()
            else:
                st.error(result["error"])


def _show_2fa_form():
    st.markdown(
        f'<div class="tfa-badge">🛡️ Verificação em duas etapas — @{st.session_state.pending_username}</div>',
        unsafe_allow_html=True,
    )

    with st.form("2fa_form"):
        code = st.text_input(
            "Código de autenticação",
            placeholder="000000",
            max_chars=8,
            help="Código de 6 dígitos do seu app de autenticação ou SMS",
        )

        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button(
                "Verificar",
                use_container_width=True,
                type="primary",
            )
        with col2:
            back = st.form_submit_button(
                "Voltar",
                use_container_width=True,
            )

        if submitted and code:
            tfa_loader = st.empty()
            with tfa_loader.container():
                loaders.radar_loader("2fa")
            result = auth.login_2fa(
                st.session_state.pending_username,
                st.session_state.pending_password,
                code.strip(),
                remember=st.session_state.pending_remember,
            )
            tfa_loader.empty()

            if result["success"]:
                st.session_state.logged_in = True
                st.session_state.login_step = "credentials"
                st.session_state.pending_password = ""
                st.session_state.setup_done = False
                st.success("Login realizado com sucesso!")
                st.rerun()
            else:
                st.error(result["error"])

        if back:
            st.session_state.login_step = "credentials"
            st.session_state.pending_password = ""
            st.rerun()


# ═══════════════════════════════════════════
# SETUP: POST-LOGIN (scrape + AI analysis + suggestions)
# ═══════════════════════════════════════════
def show_setup():
    """First-time setup: scrape user profile, AI niche analysis, suggest top creators."""
    session_user = auth.get_session_username()

    # Sidebar
    with st.sidebar:
        st.markdown(f"Logado como **@{session_user}**")
        if st.button("Sair", use_container_width=True, key="logout_setup"):
            auth.logout()
            st.session_state.logged_in = False
            st.session_state.setup_done = False
            st.session_state.niche_analysis = None
            st.session_state.suggested_profiles = []
            st.rerun()
        st.divider()

    st.markdown(
        """
        <div style="text-align: center; padding: 1rem 0;">
            <h1 style="font-size: 2.5rem;">📡 Configurando seu Radar</h1>
            <p style="color: #888;">Vamos analisar seu conteúdo e encontrar as melhores inspirações</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Step 1: Scrape the user's own profile ──
    st.subheader(f"1. Analisando seu perfil @{session_user}")

    database.add_account(session_user)

    if f"scrape_done_{session_user}" not in st.session_state:
        loader_ph = st.empty()
        with loader_ph.container():
            loaders.radar_loader("scrape_self", subtitle=f"@{session_user} — limite: 45s")

        result = scraper.scrape_account(session_user, max_posts=20)

        loader_ph.empty()

        if result["success"]:
            st.success(f"{result['posts_scraped']} posts coletados do seu perfil!")
            if result.get("error"):
                st.warning(f"Aviso: {result['error']}")
            st.session_state[f"scrape_done_{session_user}"] = True
        else:
            st.error(f"Erro na coleta: {result['error']}")
            st.warning("Você pode tentar novamente ou ir direto ao dashboard.")
            col_retry, col_skip = st.columns(2)
            with col_retry:
                if st.button("Tentar novamente", key="retry_scrape_self", use_container_width=True, type="primary"):
                    st.rerun()
            with col_skip:
                if st.button("Pular e continuar", key="skip_scrape_self", use_container_width=True):
                    st.session_state[f"scrape_done_{session_user}"] = True
                    st.rerun()
            return  # Stop here until user decides
    else:
        st.success("Perfil analisado!")

    st.divider()

    # ── Step 2: AI Niche Analysis + Creator Suggestions ──
    st.subheader("2. Identificando seu nicho e maiores creators similares")

    if st.session_state.niche_analysis is None:
        import config as _config
        if not _config.ANTHROPIC_API_KEY:
            st.warning(
                "**ANTHROPIC_API_KEY** não configurada. "
                "Configure nas variáveis de ambiente do Railway para ativar a análise com IA."
            )
            st.session_state.niche_analysis = {"niche": "", "niche_description": "", "creators": []}
        else:
            ai_status = st.empty()
            with ai_status.container():
                loaders.radar_loader("ai_analysis", subtitle="Identificando seu nicho e creators similares")

            try:
                # Get user's data for AI analysis
                posts = database.get_posts(account_username=session_user, limit=20)
                captions = [p.get("caption", "") for p in posts if p.get("caption")]
                all_hashtags = []
                for p in posts:
                    tags = p.get("hashtags", [])
                    if isinstance(tags, list):
                        all_hashtags.extend(tags)

                # Get bio from account info
                accounts = database.get_accounts()
                bio = ""
                for a in accounts:
                    if a["username"] == session_user:
                        bio = a.get("bio") or ""
                        break

                analysis = ai_generator.analyze_niche_and_suggest_creators(
                    username=session_user,
                    bio=bio,
                    captions=captions,
                    hashtags=list(set(all_hashtags)),
                    num_suggestions=5,
                )
                ai_status.empty()
                st.session_state.niche_analysis = analysis
            except Exception as e:
                ai_status.empty()
                st.error(f"Erro na análise com IA: {e}")
                st.session_state.niche_analysis = {"niche": "", "niche_description": "", "creators": []}

    analysis = st.session_state.niche_analysis

    # Show niche info
    if analysis.get("niche"):
        st.markdown(
            f"**Seu nicho:** {analysis['niche'].upper()}"
        )
        if analysis.get("niche_description"):
            st.caption(analysis["niche_description"])
        st.divider()

    # Show creator suggestions
    creators = analysis.get("creators", [])

    if creators:
        st.markdown("**Maiores creators do seu nicho para inspiração:**")
        st.caption("Esses perfis produzem conteúdo similar ao seu e podem servir como referência")

        for i, creator in enumerate(creators):
            with st.container():
                col_info, col_reason, col_action = st.columns([2, 2, 1])

                with col_info:
                    username = creator.get("username", "").strip().lstrip("@")
                    name = creator.get("name", "")
                    followers_est = creator.get("followers_estimate", "")

                    st.markdown(f"**@{username}**")
                    if name:
                        st.caption(f"{name} — {followers_est} seguidores" if followers_est else name)

                with col_reason:
                    reason = creator.get("reason", "")
                    if reason:
                        st.caption(reason)

                with col_action:
                    key = f"add_creator_{username}"
                    already_added = any(
                        a["username"] == username
                        for a in database.get_accounts()
                    )
                    if already_added:
                        st.success("No radar")
                    elif st.button("➕ Adicionar", key=key, use_container_width=True):
                        database.add_account(username)
                        st.rerun()

                st.divider()

        # Bulk actions
        col_all, col_skip = st.columns(2)
        with col_all:
            if st.button("➕ Adicionar Todos ao Radar", use_container_width=True, type="primary"):
                for creator in creators:
                    username = creator.get("username", "").strip().lstrip("@")
                    if username:
                        database.add_account(username)
                st.success("Todos adicionados!")
                st.rerun()

        with col_skip:
            if st.button("Pular sugestões", use_container_width=True):
                st.session_state.setup_done = True
                st.rerun()
    else:
        st.info(
            "Não foi possível gerar sugestões. "
            "Você pode adicionar perfis manualmente na página **Contas**."
        )

    st.divider()

    # ── Step 3: Scrape all added accounts ──
    accounts = database.get_accounts()
    added_count = len([a for a in accounts if a["username"] != session_user])

    if added_count > 0:
        st.subheader(f"3. Coletar dados ({added_count} perfis no radar)")
        st.caption("Cada perfil tem limite de 45 segundos para coleta.")

        if st.button("Coletar Todos e Ir ao Dashboard", use_container_width=True, type="primary"):
            import time as _time

            progress = st.progress(0, text="Iniciando coleta...")
            loader_ph = st.empty()
            results = []
            non_self = [a for a in accounts if a["username"] != session_user]
            total_start = _time.time()
            max_total_time = 120  # 2 min total max

            for i, account in enumerate(non_self):
                # Check total time limit
                if _time.time() - total_start > max_total_time:
                    loader_ph.warning(
                        f"Tempo total excedido (2 min). Coletados {i}/{len(non_self)} perfis. "
                        "Os demais podem ser coletados na página Contas."
                    )
                    break

                pct = i / len(non_self)
                progress.progress(
                    pct,
                    text=loaders.progress_loader(
                        "scrape_account", i, len(non_self),
                        username=account["username"],
                    ),
                )
                with loader_ph.container():
                    loaders.radar_loader(
                        "scrape_account",
                        subtitle=f"{i + 1} de {len(non_self)} perfis — limite: 45s cada",
                        username=account["username"],
                    )

                result = scraper.scrape_account(account["username"], max_posts=15)
                result["username"] = account["username"]
                results.append(result)

                # If session expired, stop and ask to re-login
                if not result["success"] and result.get("error", ""):
                    err = result["error"].lower()
                    if "sessão expirada" in err or "login" in err:
                        progress.progress(1.0, text="Coleta interrompida")
                        loader_ph.empty()
                        st.error(
                            "Sessão do Instagram expirada. Faça logout e login novamente."
                        )
                        st.session_state.setup_done = True
                        st.rerun()

            progress.progress(1.0, text=loaders.get_message("scrape_done"))
            loader_ph.empty()

            success_count = sum(1 for r in results if r["success"])
            total_posts = sum(r["posts_scraped"] for r in results)
            st.success(f"{success_count}/{len(non_self)} perfis coletados — {total_posts} posts!")

            for r in results:
                if not r["success"]:
                    st.warning(f"@{r['username']}: {r['error']}")
                elif r.get("error"):
                    st.info(f"@{r['username']}: {r['error']}")

            st.session_state.setup_done = True
            st.rerun()

    # Always show option to go to dashboard
    if st.button("Ir direto ao Dashboard", use_container_width=True):
        st.session_state.setup_done = True
        st.rerun()


# ═══════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════
def show_dashboard():
    # Sidebar: session info + logout + diagnostics
    with st.sidebar:
        session_user = auth.get_session_username()
        if session_user:
            st.markdown(f"Logado como **@{session_user}**")
            if st.button("Sair", use_container_width=True):
                auth.logout()
                st.session_state.logged_in = False
                st.session_state.setup_done = False
                st.session_state.suggested_profiles = []
                st.session_state.niche_analysis = None
                st.rerun()
            st.divider()

        # Diagnostic expander in sidebar
        with st.expander("Status do Sistema"):
            # Proxy status
            if config.PROXY_URL:
                proxy_result = auth.test_proxy()
                if proxy_result["ok"]:
                    st.success(f"Proxy OK — IP: {proxy_result['ip']}")
                else:
                    st.error(f"Proxy FALHOU: {proxy_result['error']}")
            else:
                st.warning("PROXY_URL não configurada")

            # Session status
            if st.button("Testar Sessão", use_container_width=True, key="test_session"):
                with st.spinner("Verificando sessão..."):
                    session_result = auth.verify_session()
                if session_result["valid"]:
                    st.success(f"Sessão válida: @{session_result['username']}")
                else:
                    st.error(f"Sessão inválida: {session_result['error']}")

            # API key status
            if config.ANTHROPIC_API_KEY:
                st.success("Anthropic API Key configurada")
            else:
                st.warning("ANTHROPIC_API_KEY não configurada")

    st.title("📡 Content Radar")
    st.caption("Sistema de radar de conteúdo para Instagram — análise de tendências e geração de ideias")

    st.divider()

    # Metrics row
    accounts = database.get_accounts()
    post_count = database.get_post_count()
    avg_engagement = analyzer.get_avg_engagement_rate(days=30)

    last_scraped = "Nunca"
    for acc in accounts:
        if acc.get("last_scraped_at"):
            last_scraped = acc["last_scraped_at"][:16].replace("T", " ")
            break

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Contas Monitoradas", len(accounts))
    col2.metric("Posts Coletados", post_count)
    col3.metric("Engajamento Médio", f"{avg_engagement:.2%}")
    col4.metric("Último Scrape", last_scraped)

    st.divider()

    # Main content
    if post_count == 0:
        st.info(
            "👋 **Bem-vindo ao Content Radar!** Comece adicionando contas na página "
            "**Contas** no menu lateral e execute o primeiro scrape."
        )
    else:
        left_col, right_col = st.columns([3, 2])

        with left_col:
            st.subheader("Engajamento ao Longo do Tempo")
            df = analyzer.get_posts_dataframe(days=30)
            if not df.empty and "posted_at" in df.columns:
                df = df.dropna(subset=["posted_at"])
                if not df.empty:
                    df_daily = df.set_index("posted_at").resample("D").agg(
                        avg_engagement=("engagement_rate", "mean"),
                        post_count=("id", "count"),
                    ).reset_index()

                    fig = px.line(
                        df_daily, x="posted_at", y="avg_engagement",
                        labels={"posted_at": "Data", "avg_engagement": "Engajamento Médio"},
                    )
                    fig.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
                    st.plotly_chart(fig, use_container_width=True)

        with right_col:
            st.subheader("Top 5 Posts")
            top_posts = analyzer.get_top_posts(days=30, limit=5)
            if not top_posts.empty:
                for _, post in top_posts.iterrows():
                    caption_text = str(post["caption"] or "")
                    caption_preview = (caption_text[:80] + "...") if len(caption_text) > 80 else caption_text
                    likes = int(post["likes"])
                    comments = int(post["comments"])
                    st.markdown(
                        f"**@{post['account_username']}** — "
                        f"❤️ {likes:,} 💬 {comments:,} "
                        f"({post['engagement_rate']:.2%})"
                    )
                    st.caption(caption_preview)
                    st.divider()

        # Hashtags and post types side by side
        h_col, t_col = st.columns(2)

        with h_col:
            st.subheader("Top Hashtags")
            hashtags_df = analyzer.get_top_hashtags(days=30, limit=10)
            if not hashtags_df.empty:
                fig = px.bar(
                    hashtags_df, x="count", y="hashtag", orientation="h",
                    labels={"count": "Frequência", "hashtag": ""},
                )
                fig.update_layout(
                    height=300, margin=dict(l=0, r=0, t=10, b=0),
                    yaxis=dict(autorange="reversed"),
                )
                st.plotly_chart(fig, use_container_width=True)

        with t_col:
            st.subheader("Tipos de Post")
            type_df = analyzer.get_post_type_distribution(days=30)
            if not type_df.empty:
                fig = px.pie(
                    type_df, values="count", names="post_type",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════
# ROUTING
# ═══════════════════════════════════════════
if not st.session_state.logged_in:
    show_login()
elif not st.session_state.setup_done and database.get_post_count() == 0:
    show_setup()
else:
    show_dashboard()
