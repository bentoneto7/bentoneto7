import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import streamlit as st

import config
from core import database, auth, meta_ads
from core.page_guard import require_login


# ── Conditional formatting helpers ───────────────────────────────────────────

def badge(text: str, color: str) -> str:
    """Return an HTML colored badge."""
    colors = {
        "green":  ("#d4edda", "#155724"),
        "yellow": ("#fff3cd", "#856404"),
        "red":    ("#f8d7da", "#721c24"),
        "blue":   ("#d1ecf1", "#0c5460"),
        "gray":   ("#e2e3e5", "#383d41"),
    }
    bg, fg = colors.get(color, colors["gray"])
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 10px;'
        f'border-radius:12px;font-size:0.8rem;font-weight:600;">{text}</span>'
    )


def status_badge(status: str) -> str:
    if status == "ACTIVE":
        return badge("● ATIVA", "green")
    if status == "PAUSED":
        return badge("⏸ PAUSADA", "yellow")
    if status == "ARCHIVED":
        return badge("✕ ARQUIVADA", "gray")
    return badge(status, "gray")


def ctr_badge(ctr: float) -> str:
    """CTR benchmark: >2% good, 1-2% ok, <1% bad."""
    if ctr >= 2.0:
        return badge(f"CTR {ctr:.2f}% ▲", "green")
    if ctr >= 1.0:
        return badge(f"CTR {ctr:.2f}% →", "yellow")
    return badge(f"CTR {ctr:.2f}% ▼", "red")


def cpc_badge(cpc: float, product_price: float = 0.0, currency: str = "R$") -> str:
    """
    Custo por venda vs. valor do produto:
      ≤ 30% do preço → verde (bom)
      31–50%         → amarelo (médio)
      > 50%          → vermelho (ruim)
    Se product_price não for informado, usa limites fixos R$1 / R$3.
    """
    if cpc == 0:
        return badge("Custo —", "gray")
    if product_price > 0:
        pct = (cpc / product_price) * 100
        label = f"Custo {currency}{cpc:.2f} ({pct:.0f}% do prod.)"
        if pct <= 30:
            return badge(f"{label} ▲", "green")
        if pct <= 50:
            return badge(f"{label} →", "yellow")
        return badge(f"{label} ▼", "red")
    # fallback sem preço configurado
    if cpc < 1.0:
        return badge(f"CPC {currency}{cpc:.2f} ▲", "green")
    if cpc <= 3.0:
        return badge(f"CPC {currency}{cpc:.2f} →", "yellow")
    return badge(f"CPC {currency}{cpc:.2f} ▼", "red")


def spend_badge(spend: float, daily_budget: float, currency: str = "R$") -> str:
    """Spend vs budget: >70% good delivery, 30-70% ok, <30% underdelivering."""
    if daily_budget <= 0:
        return badge(f"Gasto {currency}{spend:.2f}", "gray")
    pct = (spend / daily_budget) * 100
    if pct >= 70:
        return badge(f"Gasto {currency}{spend:.2f} ({pct:.0f}%)", "green")
    if pct >= 30:
        return badge(f"Gasto {currency}{spend:.2f} ({pct:.0f}%)", "yellow")
    return badge(f"Gasto {currency}{spend:.2f} ({pct:.0f}%) ⚠", "red")


def impressions_badge(impressions: int) -> str:
    if impressions >= 10000:
        return badge(f"{impressions:,} impressões ▲", "green")
    if impressions >= 1000:
        return badge(f"{impressions:,} impressões →", "yellow")
    if impressions == 0:
        return badge("Sem impressões", "gray")
    return badge(f"{impressions:,} impressões ▼", "red")

database.init_db()

st.set_page_config(page_title="Meta Ads | Content Radar", page_icon="📡", layout="wide")
require_login()

# Sidebar: session info + product price config
with st.sidebar:
    session_user = auth.get_session_username()
    if session_user:
        st.markdown(f"Logado como **@{session_user}**")
        if st.button("Sair", use_container_width=True, key="logout_ads"):
            auth.logout()
            st.session_state.logged_in = False
            st.rerun()
        st.divider()

    st.markdown("### ⚙️ Parâmetro de Performance")

    # Load saved price from DB on first render
    if "product_price" not in st.session_state:
        saved = database.get_config("product_price", "0")
        st.session_state["product_price"] = float(saved)

    product_price = st.number_input(
        "Valor do produto / serviço (R$):",
        min_value=0.0,
        value=st.session_state["product_price"],
        step=10.0,
        help="≤30% do valor = bom · 31–50% = médio · >50% = ruim",
        key="product_price_input",
    )

    # Persist whenever the value changes
    if product_price != st.session_state["product_price"]:
        st.session_state["product_price"] = product_price
        database.set_config("product_price", str(product_price))

    if product_price > 0:
        st.caption(
            f"🟢 Bom: até R$ {product_price * 0.30:.2f}\n\n"
            f"🟡 Médio: até R$ {product_price * 0.50:.2f}\n\n"
            f"🔴 Ruim: acima de R$ {product_price * 0.50:.2f}"
        )
    st.divider()

st.title("📢 Meta Ads")
st.caption("Gerencie e crie campanhas pagas a partir das suas ideias de conteúdo")

# --- Check credentials ---
has_credentials = bool(
    config.META_ACCESS_TOKEN and
    config.META_AD_ACCOUNT_ID and
    config.META_APP_ID and
    config.META_APP_SECRET
)

if not has_credentials:
    st.warning(
        "**Credenciais Meta Ads não configuradas.** "
        "Adicione as variáveis `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID`, "
        "`META_APP_ID` e `META_APP_SECRET` ao seu arquivo `.env`."
    )
    st.stop()

# --- Init API ---
@st.cache_data(ttl=300)
def load_account_info():
    return meta_ads.get_account_info()

@st.cache_data(ttl=60)
def load_campaigns():
    return meta_ads.get_campaigns()

# --- Connection status + account overview ---
try:
    account_info = load_account_info()
    connection_ok = True
except Exception as e:
    connection_ok = False
    account_error = str(e)

if not connection_ok:
    st.error(f"Erro ao conectar com a Meta API: {account_error}")
    st.stop()

# Account overview cards
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Conta", account_info["name"])
with col2:
    st.metric("Status", account_info["status"])
with col3:
    st.metric("Moeda", account_info["currency"])
with col4:
    st.metric("Fuso Horário", account_info["timezone"])

st.success("Conectado à Meta API com sucesso.")
st.divider()

# --- Tabs ---
tab_campaigns, tab_create, tab_history = st.tabs(
    ["📊 Campanhas", "🚀 Criar Campanha", "📁 Histórico Local"]
)

# ── Tab 1: Campaigns ──────────────────────────────────────────────────────────
with tab_campaigns:
    refresh_col, _ = st.columns([1, 4])
    with refresh_col:
        if st.button("🔄 Atualizar", key="refresh_campaigns"):
            load_campaigns.clear()
            st.rerun()

    try:
        campaigns = load_campaigns()
    except Exception as e:
        st.error(f"Erro ao carregar campanhas: {e}")
        campaigns = []

    if not campaigns:
        st.info("Nenhuma campanha encontrada nesta conta.")
    else:
        objective_labels = {
            "OUTCOME_ENGAGEMENT": "Engajamento",
            "OUTCOME_TRAFFIC": "Tráfego",
            "OUTCOME_LEADS": "Leads",
            "OUTCOME_AWARENESS": "Reconhecimento",
            "OUTCOME_APP_PROMOTION": "App",
            "OUTCOME_SALES": "Vendas",
        }

        for camp in campaigns:
            status = camp["status"]
            objective_label = objective_labels.get(camp["objective"], camp["objective"])

            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 1])

                with c1:
                    st.markdown(
                        f"{status_badge(status)} &nbsp; **{camp['name']}**",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"ID: `{camp['campaign_id']}` · Criada em: {camp['created_time'][:10]}")

                with c2:
                    st.metric("Objetivo", objective_label)

                with c3:
                    budget = camp["daily_budget"]
                    st.metric("Budget/dia", f"R$ {budget:.2f}" if budget else "—")

                with c4:
                    if st.button("📈 Métricas", key=f"insights_{camp['campaign_id']}"):
                        toggled = not st.session_state.get(f"show_insights_{camp['campaign_id']}", False)
                        st.session_state[f"show_insights_{camp['campaign_id']}"] = toggled

                with c5:
                    if status == "ACTIVE":
                        if st.button("⏸ Pausar", key=f"pause_{camp['campaign_id']}"):
                            with st.spinner("Pausando..."):
                                ok = meta_ads.update_campaign_status(camp["campaign_id"], "PAUSED")
                            if ok:
                                load_campaigns.clear()
                                st.success("Campanha pausada.")
                                st.rerun()
                            else:
                                st.error("Falha ao pausar campanha.")
                    else:
                        if st.button("▶ Ativar", key=f"activate_{camp['campaign_id']}"):
                            with st.spinner("Ativando..."):
                                ok = meta_ads.update_campaign_status(camp["campaign_id"], "ACTIVE")
                            if ok:
                                load_campaigns.clear()
                                st.success("Campanha ativada.")
                                st.rerun()
                            else:
                                st.error("Falha ao ativar campanha.")

                # ── Campaign insights ─────────────────────────────────────
                if st.session_state.get(f"show_insights_{camp['campaign_id']}"):
                    with st.expander("📊 Métricas da Campanha", expanded=True):
                        period = st.selectbox(
                            "Período",
                            ["today", "last_7_d", "last_30_d"],
                            format_func=lambda x: {
                                "today": "Hoje",
                                "last_7_d": "Últimos 7 dias",
                                "last_30_d": "Últimos 30 dias",
                            }[x],
                            key=f"period_{camp['campaign_id']}",
                        )
                        try:
                            with st.spinner("Carregando métricas..."):
                                ins = meta_ads.get_campaign_insights(camp["campaign_id"], period)
                            m1, m2, m3, m4, m5, m6 = st.columns(6)
                            m1.metric("Impressões", f"{ins['impressions']:,}")
                            m2.metric("Cliques", f"{ins['clicks']:,}")
                            m3.metric("Alcance", f"{ins['reach']:,}")
                            m4.metric("Gasto (R$)", f"{ins['spend']:.2f}")
                            m5.metric("CTR", f"{ins['ctr']:.2f}%")
                            m6.metric("CPC (R$)", f"{ins['cpc']:.2f}")

                            st.markdown(
                                "&nbsp;&nbsp;".join([
                                    ctr_badge(ins["ctr"]),
                                    cpc_badge(ins["cpc"], product_price),
                                    spend_badge(ins["spend"], camp["daily_budget"]),
                                    impressions_badge(ins["impressions"]),
                                ]),
                                unsafe_allow_html=True,
                            )

                            database.update_meta_campaign_metrics(
                                camp["campaign_id"],
                                {**ins, "status": camp["status"]},
                            )
                        except Exception as e:
                            st.warning(f"Sem dados de insights: {e}")

                # ── Ad Sets ───────────────────────────────────────────────
                with st.expander(f"📦 Conjuntos de Anúncios", expanded=False):
                    try:
                        with st.spinner("Carregando conjuntos..."):
                            ad_sets = meta_ads.get_ad_sets(camp["campaign_id"])

                        if not ad_sets:
                            st.info("Nenhum conjunto encontrado nesta campanha.")
                        else:
                            adset_period = st.selectbox(
                                "Período (conjuntos)",
                                ["today", "last_7_d", "last_30_d"],
                                format_func=lambda x: {
                                    "today": "Hoje",
                                    "last_7_d": "Últimos 7 dias",
                                    "last_30_d": "Últimos 30 dias",
                                }[x],
                                key=f"adset_period_{camp['campaign_id']}",
                            )

                            for adset in ad_sets:
                                as_status = adset["status"]
                                as_budget = adset["daily_budget"]

                                a1, a2, a3, a4 = st.columns([3, 1, 1, 1])
                                with a1:
                                    st.markdown(
                                        f"{status_badge(as_status)} &nbsp; **{adset['name']}**",
                                        unsafe_allow_html=True,
                                    )
                                    st.caption(
                                        f"ID: `{adset['adset_id']}` · "
                                        f"Meta: {adset['optimization_goal']}"
                                    )
                                with a2:
                                    st.metric("Budget/dia", f"R$ {as_budget:.2f}" if as_budget else "—")
                                with a3:
                                    if as_status == "ACTIVE":
                                        if st.button("⏸ Pausar", key=f"pause_as_{adset['adset_id']}"):
                                            meta_ads.update_adset_status(adset["adset_id"], "PAUSED")
                                            st.rerun()
                                    else:
                                        if st.button("▶ Ativar", key=f"act_as_{adset['adset_id']}"):
                                            meta_ads.update_adset_status(adset["adset_id"], "ACTIVE")
                                            st.rerun()
                                with a4:
                                    load_ins = st.button("📈", key=f"ins_as_{adset['adset_id']}")

                                if load_ins:
                                    try:
                                        as_ins = meta_ads.get_adset_insights(adset["adset_id"], adset_period)
                                        ai1, ai2, ai3, ai4, ai5, ai6 = st.columns(6)
                                        ai1.metric("Impressões", f"{as_ins['impressions']:,}")
                                        ai2.metric("Cliques", f"{as_ins['clicks']:,}")
                                        ai3.metric("Alcance", f"{as_ins['reach']:,}")
                                        ai4.metric("Gasto", f"R$ {as_ins['spend']:.2f}")
                                        ai5.metric("CTR", f"{as_ins['ctr']:.2f}%")
                                        ai6.metric("CPC", f"R$ {as_ins['cpc']:.2f}")
                                        st.markdown(
                                            "&nbsp;&nbsp;".join([
                                                ctr_badge(as_ins["ctr"]),
                                                cpc_badge(as_ins["cpc"], product_price),
                                                spend_badge(as_ins["spend"], as_budget),
                                                impressions_badge(as_ins["impressions"]),
                                            ]),
                                            unsafe_allow_html=True,
                                        )
                                    except Exception as e:
                                        st.warning(f"Sem insights: {e}")

                                st.divider()
                    except Exception as e:
                        st.warning(f"Erro ao carregar conjuntos: {e}")

# ── Tab 2: Create campaign ────────────────────────────────────────────────────
with tab_create:
    st.subheader("Criar Campanha a partir de uma Ideia")

    ideas = database.get_ideas()
    if not ideas:
        st.info("Nenhuma ideia disponível. Gere ideias na página **Ideias** primeiro.")
    else:
        format_icons = {
            "image": "🖼️", "video": "🎬", "carousel": "🎠", "reel": "🎞️",
        }

        # Idea selector
        idea_labels = {
            idea["id"]: f"{format_icons.get(idea.get('suggested_format', ''), '📝')} {idea['title']}"
            for idea in ideas
        }
        selected_idea_id = st.selectbox(
            "Selecionar ideia:",
            options=list(idea_labels.keys()),
            format_func=lambda x: idea_labels[x],
        )

        selected_idea = next((i for i in ideas if i["id"] == selected_idea_id), None)

        if selected_idea:
            with st.container(border=True):
                st.markdown(f"**{selected_idea['title']}**")
                st.markdown(selected_idea.get("description", ""))
                hashtags = selected_idea.get("suggested_hashtags", [])
                if hashtags:
                    st.markdown("**Hashtags:** " + " ".join(f"`#{h.lstrip('#')}`" for h in hashtags))
                fmt = selected_idea.get("suggested_format", "")
                if fmt:
                    st.caption(f"Formato sugerido: {fmt.capitalize()}")

        st.divider()

        col_a, col_b = st.columns(2)

        with col_a:
            campaign_name = st.text_input(
                "Nome da campanha:",
                value=selected_idea["title"][:70] if selected_idea else "",
                max_chars=70,
            )

            objective = st.selectbox(
                "Objetivo:",
                ["OUTCOME_ENGAGEMENT", "OUTCOME_TRAFFIC", "OUTCOME_LEADS", "OUTCOME_AWARENESS"],
                format_func=lambda x: {
                    "OUTCOME_ENGAGEMENT": "Engajamento",
                    "OUTCOME_TRAFFIC": "Tráfego",
                    "OUTCOME_LEADS": "Leads",
                    "OUTCOME_AWARENESS": "Reconhecimento de marca",
                }[x],
            )

            budget_brl = st.number_input(
                "Budget diário (R$):",
                min_value=1.0,
                max_value=10000.0,
                value=10.0,
                step=1.0,
            )

        with col_b:
            country_options = {"BR": "Brasil 🇧🇷", "US": "EUA 🇺🇸", "PT": "Portugal 🇵🇹"}
            selected_countries = st.multiselect(
                "Países:",
                options=list(country_options.keys()),
                default=["BR"],
                format_func=lambda x: country_options.get(x, x),
            )

            age_col1, age_col2 = st.columns(2)
            with age_col1:
                age_min = st.number_input("Idade mínima:", min_value=13, max_value=64, value=18)
            with age_col2:
                age_max = st.number_input("Idade máxima:", min_value=14, max_value=65, value=65)

        st.markdown("")

        if st.button("🚀 Criar Campanha", type="primary", use_container_width=True):
            if not selected_idea:
                st.error("Selecione uma ideia primeiro.")
            elif not campaign_name.strip():
                st.error("Nome da campanha não pode estar vazio.")
            elif not selected_countries:
                st.error("Selecione pelo menos um país.")
            elif age_min >= age_max:
                st.error("A idade mínima deve ser menor que a máxima.")
            else:
                idea_to_use = dict(selected_idea)
                idea_to_use["title"] = campaign_name.strip()

                with st.spinner("Criando campanha na Meta..."):
                    try:
                        result = meta_ads.create_campaign_from_idea(
                            idea=idea_to_use,
                            budget_brl=budget_brl,
                            objective=objective,
                            countries=selected_countries,
                            age_min=age_min,
                            age_max=age_max,
                        )

                        # Save to local DB
                        database.save_meta_campaign({
                            "campaign_id": result["campaign_id"],
                            "name": result["name"],
                            "status": "PAUSED",
                            "objective": objective,
                            "idea_id": selected_idea["id"],
                            "daily_budget": budget_brl,
                        })

                        load_campaigns.clear()

                        st.success(
                            f"Campanha **{result['name']}** criada com sucesso! "
                            f"ID: `{result['campaign_id']}`"
                        )
                        st.info(
                            "A campanha foi criada como **PAUSADA**. "
                            "Ative-a na aba **Campanhas** quando estiver pronta para veicular."
                        )

                    except Exception as e:
                        st.error(f"Erro ao criar campanha: {e}")

# ── Tab 3: Local history ──────────────────────────────────────────────────────
with tab_history:
    st.subheader("Campanhas Criadas pelo App")

    local_campaigns = database.get_meta_campaigns()

    if not local_campaigns:
        st.info("Nenhuma campanha criada pelo app ainda. Use a aba **Criar Campanha** para começar.")
    else:
        objective_labels = {
            "OUTCOME_ENGAGEMENT": "Engajamento",
            "OUTCOME_TRAFFIC": "Tráfego",
            "OUTCOME_LEADS": "Leads",
            "OUTCOME_AWARENESS": "Reconhecimento",
        }

        for camp in local_campaigns:
            status = camp["status"]
            status_badge = "🟢" if status == "ACTIVE" else "🔴" if status == "PAUSED" else "⚪"
            updated = camp.get("updated_at", "")[:16].replace("T", " ")

            with st.container(border=True):
                h_col, d_col, btn_col = st.columns([3, 3, 1])

                with h_col:
                    st.markdown(
                        f"{status_badge(status)} &nbsp; **{camp['name']}**",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"ID: `{camp['campaign_id']}`")
                    obj_label = objective_labels.get(camp.get("objective", ""), camp.get("objective", ""))
                    st.caption(f"Objetivo: {obj_label} · Atualizado: {updated}")

                with d_col:
                    impressions_val = camp.get("impressions", 0)
                    clicks_val = camp.get("clicks", 0)
                    spend_val = float(camp.get("spend", 0))
                    budget_val = float(camp.get("daily_budget", 0))
                    ctr_val = (clicks_val / impressions_val * 100) if impressions_val > 0 else 0.0
                    cpc_val = (spend_val / clicks_val) if clicks_val > 0 else 0.0

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Impressões", f"{impressions_val:,}")
                    m2.metric("Cliques", f"{clicks_val:,}")
                    m3.metric("Alcance", f"{camp.get('reach', 0):,}")
                    m4.metric("Gasto", f"R$ {spend_val:.2f}")

                    st.markdown(
                        "&nbsp;&nbsp;".join([
                            ctr_badge(ctr_val),
                            cpc_badge(cpc_val, product_price),
                            spend_badge(spend_val, budget_val),
                            impressions_badge(impressions_val),
                        ]),
                        unsafe_allow_html=True,
                    )

                with btn_col:
                    meta_url = f"https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={config.META_AD_ACCOUNT_ID.replace('act_', '')}"
                    st.link_button("Ver no Meta", meta_url, use_container_width=True)

                    if st.button("🗑 Remover", key=f"del_{camp['campaign_id']}", use_container_width=True):
                        database.delete_meta_campaign(camp["campaign_id"])
                        st.rerun()
