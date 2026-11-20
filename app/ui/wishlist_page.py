import sqlite3

import streamlit as st

from app.db.products import get_products_by_ids
from app.ui.product_card import _render_product
from app.db.user_data import get_wishlist
from app.shopping.identity import require_authenticated_user

def _render_wishlist() -> None:
    st.header("Your wishlist")
    st.info(
        "This wishlist is temporary and stored only in this browser session."
    )

    if not st.session_state.wishlist:
        if st.session_state.access_mode == "authenticated":
            try:
                user_id = require_authenticated_user(st.session_state)
                persistent_ids = {row["id"] for row in get_wishlist(user_id)}
                st.session_state.wishlist.update(persistent_ids)
            except (PermissionError, OSError, sqlite3.Error):
                pass
        if not st.session_state.wishlist:
            st.write("No saved products yet.")
            return

    try:
        rows = get_products_by_ids(list(st.session_state.wishlist))
    except (OSError, sqlite3.Error, ValueError):
        st.error("The wishlist could not be loaded from the catalog.")
        return

    products_by_id = {product["id"]: product for product in rows}
    missing = st.session_state.wishlist - products_by_id.keys()

    if missing:
        st.warning("One or more saved products are no longer available.")

    columns = st.columns(3, gap="medium")

    for index, product in enumerate(rows):
        with columns[index % len(columns)]:
            _render_product(product, grid_view=True)
