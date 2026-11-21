import sqlite3
import logging

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
from app.db.schema import validate_account_schema, validate_shopping_schema
from app.ui.address_pages import _render_addresses
from app.ui.orders_page import _render_orders
from app.ui.order_detail_page import _render_order_detail
from app.ui.comparison_page import _render_comparison
from app.db.user_data import get_cart, set_cart_quantity
from app.observability import configure_logging, log_failure

def _render_login_screen() -> None:
    render_login_screen()

def _inject_store_styles() -> None:
    render_store_styles()

def main() -> None:
    configure_logging()
    st.set_page_config(page_title="Shopwise", page_icon="🛍️", layout="wide")
    try:
        validate_shopping_schema()
        validate_account_schema()
    except (OSError, sqlite3.Error, RuntimeError) as error:
        log_failure("startup_schema_validation_failed", error)
        st.error("Shopwise could not connect to its data store. Please try again later.")
        return

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


    if st.session_state.access_mode == "authenticated":
        user_id = st.session_state.get("authenticated_user_id")
        if isinstance(user_id, str) and st.session_state.get("_cart_synced_user_id") != user_id:
            try:
                guest_cart = dict(st.session_state.cart)
                persisted_rows = get_cart(user_id)
                merged_cart = {
                    int(row["product_id"]): int(row["quantity"])
                    for row in persisted_rows
                    if row["product"] is not None
                }
                for product_id, quantity in guest_cart.items():
                    merged_cart[product_id] = int(merged_cart.get(product_id, 0)) + int(quantity)
                for product_id, quantity in merged_cart.items():
                    set_cart_quantity(user_id, product_id, quantity)
                st.session_state.cart = merged_cart
                st.session_state["_cart_synced_user_id"] = user_id
            except (PermissionError, OSError, sqlite3.Error) as error:
                log_failure("cart_sync_failed", error, level=logging.WARNING)
                st.session_state["_cart_synced_user_id"] = None

    _render_store_header()

    try:
        facets = catalog_ui.load_catalog_facets()
    except (OSError, sqlite3.Error) as error:
        log_failure("catalog_facets_load_failed", error)
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
    elif page == "addresses" and st.session_state.access_mode == "authenticated":
        _render_addresses()
    elif page == "orders" and st.session_state.access_mode == "authenticated":
        _render_orders()
    elif page.startswith("order-detail:") and st.session_state.access_mode == "authenticated":
        _render_order_detail(int(page.split(":", 1)[1]))
    elif page == "compare":
        _render_comparison()
    else:
        st.session_state.store_page = "shop"
        catalog_ui._render_shop(facets)

    _render_chat_launcher()

if __name__ == "__main__":
    main()
