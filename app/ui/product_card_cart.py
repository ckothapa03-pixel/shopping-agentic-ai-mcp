import sqlite3
from typing import Any

import streamlit as st

from app.db.user_data import remove_cart_item, set_cart_quantity
from app.ui.error_messages import safe_error_message


def update_card_cart_quantity(product: dict[str, Any], quantity: int) -> None:
    product_id = int(product["id"])
    stock = int(product["stock"])
    if quantity < 0 or quantity > stock:
        raise ValueError("Quantity cannot exceed available stock")
    if st.session_state.access_mode == "authenticated":
        user_id = st.session_state.get("authenticated_user_id")
        if user_id:
            if quantity == 0:
                remove_cart_item(user_id, product_id)
            else:
                set_cart_quantity(user_id, product_id, quantity)
    updated = dict(st.session_state.cart)
    if quantity == 0:
        updated.pop(product_id, None)
    else:
        updated[product_id] = quantity
    st.session_state.cart = updated
    st.session_state.demo_checkout_complete = False


def render_cart_quantity_controls(product: dict[str, Any]) -> bool:
    product_id = int(product["id"])
    stock = int(product["stock"])
    quantity = int(st.session_state.cart.get(product_id, 0))
    if quantity < 1:
        return False
    product_name = str(product.get("name") or "this product")
    with st.container(key=f"cart-quantity-controls-{product_id}"):
        controls = st.columns([1, 1.25, 1], gap="small")
        decrease = controls[0].button(
            "−",
            key=f"decrease-cart-{product_id}",
            help=f"Decrease {product_name} quantity in your cart",
            width="stretch",
        )
        controls[1].markdown(
            f'<div class="st-key-cart-quantity-value">{quantity}</div>',
            unsafe_allow_html=True,
        )
        increase = controls[2].button(
            "+",
            key=f"increase-cart-{product_id}",
            disabled=quantity >= stock,
            help=f"Increase {product_name} quantity in your cart",
            width="stretch",
        )
    if decrease:
        try:
            update_card_cart_quantity(product, quantity - 1)
            st.toast(f"Cart quantity updated for {product['name']}.")
            st.rerun()
        except (PermissionError, ValueError, OSError, sqlite3.Error) as error:
            st.error(safe_error_message(error, "The cart could not be updated.", event="cart_quantity_update_failed", allow_value_error=True))
    if increase:
        try:
            update_card_cart_quantity(product, quantity + 1)
            st.toast(f"Cart quantity updated for {product['name']}.")
            st.rerun()
        except (PermissionError, ValueError, OSError, sqlite3.Error) as error:
            st.error(safe_error_message(error, "The cart could not be updated.", event="cart_quantity_update_failed", allow_value_error=True))
    return True
