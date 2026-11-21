import sqlite3
import streamlit as st

from app.db.order_repository import cancel_order, get_order
from app.shopping.identity import require_authenticated_user
from app.shopping.confirmation import (
    confirmation_matches,
    consume_confirmation,
    request_confirmation,
)
from app.ui.error_messages import safe_error_message


def _render_order_detail(order_id: int) -> None:
    st.header(f"Order #{order_id}")
    try:
        user_id = require_authenticated_user(st.session_state)
        detail = get_order(user_id, order_id)
    except (PermissionError, OSError, sqlite3.Error) as error:
        st.error(safe_error_message(error, "Order details could not be loaded.", event="order_detail_load_failed"))
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
        confirmation_key = "pending_cancel_order_confirmation"
        parameters = {"order_id": order_id, "status": order["status"]}
        is_confirming = confirmation_matches(
            st.session_state,
            confirmation_key,
            "cancel_order",
            user_id,
            parameters,
        )
        if is_confirming:
            st.warning(f"Confirm cancellation of order #{order_id}.")
            if st.button(
                f"Confirm cancellation · Order #{order_id}",
                type="secondary",
            ):
                approved = consume_confirmation(
                    st.session_state,
                    confirmation_key,
                    "cancel_order",
                    user_id,
                    parameters,
                )
                if not approved:
                    st.error("Cancellation confirmation expired. Review again.")
                else:
                    try:
                        cancel_order(user_id, order_id)
                        st.success("Order cancelled.")
                        st.rerun()
                    except (PermissionError, ValueError, sqlite3.Error, OSError) as error:
                        st.error(safe_error_message(error, "The order could not be cancelled.", event="order_cancellation_failed", allow_value_error=True))
            if st.button("Keep this order", key=f"keep-order-{order_id}"):
                st.session_state.pop(confirmation_key, None)
                st.rerun()
        elif st.button("Cancel order", type="secondary"):
            request_confirmation(
                st.session_state,
                confirmation_key,
                "cancel_order",
                user_id,
                parameters,
            )
            st.rerun()
