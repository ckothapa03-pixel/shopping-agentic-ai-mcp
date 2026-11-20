import sqlite3
import streamlit as st

from app.db.order_repository import list_orders
from app.shopping.identity import require_authenticated_user


def _render_orders() -> None:
    st.header("Your orders")
    try:
        user_id = require_authenticated_user(st.session_state)
        status = st.selectbox("Status", ["All", "PLACED", "CONFIRMED", "SHIPPED", "DELIVERED", "CANCELLED"])
        orders = list_orders(user_id, None if status == "All" else status)
    except (PermissionError, OSError, sqlite3.Error, ValueError) as error:
        st.error(str(error))
        return
    if not orders:
        st.info("No orders found.")
        return
    for order in orders:
        with st.container(border=True):
            st.write(f"**Order #{order['id']}**")
            st.write(f"{order['created_at']} · {order['status']} · ₹{order['total']:,.2f}")
            if st.button("View details", key=f"view-order-{order['id']}"):
                st.session_state.store_page = f"order-detail:{order['id']}"
                st.rerun()
