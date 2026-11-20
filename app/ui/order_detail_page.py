import sqlite3
import streamlit as st

from app.db.order_repository import cancel_order, get_order
from app.shopping.identity import require_authenticated_user


def _render_order_detail(order_id: int) -> None:
    st.header(f"Order #{order_id}")
    try:
        user_id = require_authenticated_user(st.session_state)
        detail = get_order(user_id, order_id)
    except (PermissionError, OSError, sqlite3.Error) as error:
        st.error(str(error))
        return
    if detail is None:
        st.error("Order not found.")
        return
    order = detail["order"]
    st.write(f"Status: **{order['status']}**")
    st.write(f"Placed: {order['created_at']}")
    st.write(f"Payment: {order['payment_method']}")
    for item in detail["items"]:
        st.write(f"{item['name']} · {item['quantity']} × ₹{item['unit_price']:,.2f}")
    st.markdown(
        f"Subtotal ₹{order['subtotal']:,.2f} · Discount ₹{order['discount']:,.2f} · "
        f"Shipping ₹{order['shipping_fee']:,.2f} · Total ₹{order['total']:,.2f}"
    )
    address = detail["address"]
    if address:
        st.subheader("Delivery address")
        st.write(address["label"], address["line1"], address["city"], address["state"], address["pincode"])
    if order["status"] in {"PLACED", "CONFIRMED"}:
        if st.button("Cancel order", type="secondary"):
            try:
                cancel_order(user_id, order_id)
                st.success("Order cancelled.")
                st.rerun()
            except (PermissionError, ValueError, sqlite3.Error, OSError) as error:
                st.error(str(error))
