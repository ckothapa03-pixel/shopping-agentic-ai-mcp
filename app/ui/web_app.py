import sqlite3

import streamlit as st

from app.ui import catalog as catalog_ui
from app.ui.auth import render_login_screen
from app.ui.styles import render_store_styles
from app.ui.store_navigation import _render_store_header
from app.ui.account_pages import _render_profile, _render_settings
from app.ui.cart_pages import _render_cart
from app.ui.checkout_page import _render_demo_checkout
from app.ui.chat.chat import _render_chat_launcher
from app.ui.wishlist_page import _render_wishlist

def _render_login_screen() -> None:
    render_login_screen()

def _inject_store_styles() -> None:
    render_store_styles()

def main() -> None:
    st.set_page_config(page_title="Shopwise", page_icon="🛍️", layout="wide")

    if st.session_state.get("access_mode") not in {"guest", "authenticated"}:
        _render_login_screen()
        return

    _inject_store_styles()

    for key, initial_value in (
        ("cart", {}),
        ("wishlist", set()),
        ("chat_messages", []),
        ("chat_pending_reply", None),
        ("chat_processing", False),
        ("agent_history", []),
        ("chat_open", False),
        ("store_page", "shop"),
        ("catalog_view", False),
        ("demo_checkout_complete", False),
        ("catalog_search_query", ""),
        ("catalog_page", 1),
        ("catalog_layout_preference", "Grid"),
    ):
        if key not in st.session_state:
            st.session_state[key] = initial_value

    _render_store_header()

    try:
        facets = catalog_ui.load_catalog_facets()
    except (OSError, sqlite3.Error):
        st.error("Shopwise could not load product categories. Please try again.")
        return

    page = st.session_state.store_page

    if page == "cart":
        _render_cart()
    elif page == "checkout":
        _render_demo_checkout()
    elif page == "wishlist":
        _render_wishlist()
    elif page == "profile" and st.session_state.access_mode == "authenticated":
        _render_profile()
    elif page == "settings" and st.session_state.access_mode == "authenticated":
        _render_settings()
    else:
        st.session_state.store_page = "shop"
        catalog_ui._render_shop(facets)

    _render_chat_launcher()

if __name__ == "__main__":
    main()
