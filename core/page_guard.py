import streamlit as st

from core import auth


def require_login():
    """Block page access if not logged in. Call at the top of every page."""
    auth.restore_session_from_env()

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = auth.is_logged_in()

    if not st.session_state.logged_in:
        st.warning("Faça login na **página principal** para acessar esta seção.")
        st.page_link("app.py", label="Ir para Login", icon="🔑")
        st.stop()
