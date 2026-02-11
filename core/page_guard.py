import streamlit as st

from core import auth


def require_login():
    """Block page access if not logged in. Call at the top of every page."""
    auth.restore_session_from_env()

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = auth.is_logged_in()

    if not st.session_state.logged_in:
        st.markdown(
            """
            <div style="text-align: center; padding: 4rem 0;">
                <h2>🔒 Acesso Restrito</h2>
                <p style="color: #888; font-size: 1.1rem;">
                    Faça login na página principal para acessar o Content Radar
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.page_link("app.py", label="Ir para Login", icon="🔑", use_container_width=True)

        st.stop()
