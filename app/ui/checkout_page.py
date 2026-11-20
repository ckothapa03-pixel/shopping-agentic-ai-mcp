import sqlite3

from decimal import Decimal

import streamlit as st

from app.shopping.cart import validate_checkout
from app.ui.catalog import _load_cart_products
from app.db.address_repository import list_addresses
from app.db.checkout_repository import create_order
from app.shopping.identity import require_authenticated_user

def _render_demo_checkout() -> None:
    st.header("Checkout")
    if st.session_state.access_mode != "authenticated":
        st.error("Sign in to place an order.")
        return
    try:
        user_id = require_authenticated_user(st.session_state)
        addresses = list_addresses(user_id)
    except (PermissionError, OSError, sqlite3.Error) as error:
        st.error(str(error))
        return
    if not addresses:
        st.warning("Add a delivery address before checkout.")
        if st.button("Manage addresses"):
            st.session_state.store_page = "addresses"
            st.rerun()
        return

    if not st.session_state.cart:
        st.info("Your cart is empty. Add products before reviewing checkout.")
        return

    products_by_id = _load_cart_products()
    if products_by_id is None:
        return

    for product_id in st.session_state.cart:
        if product_id not in products_by_id:
            st.error("A cart item is no longer available. Remove it before checkout.")
            return

    try:
        total = validate_checkout(st.session_state.cart, products_by_id)
    except (KeyError, ValueError) as error:
        st.error(f"Your cart needs attention before checkout: {error}")
        return

    st.subheader("Order summary")

    for product_id, quantity in st.session_state.cart.items():
        product = products_by_id[product_id]
        line_total = Decimal(str(product["price"])) * quantity
        st.write(
            f"{product['name']} · {quantity} × "
            f"₹{product['price']:,.2f} = ₹{line_total:,.2f}"
        )

    st.markdown(f"### Total: ₹{total:,.2f}")

    address_labels = {
        f"{address['label']} - {address['line1']}, {address['city']}": address["id"]
        for address in addresses
    }
    selected_address = st.selectbox("Delivery address", list(address_labels))
    payment_method = st.selectbox("Payment method", ["COD"])
    coupon_code = st.text_input("Coupon code").strip() or None

    if st.session_state.demo_checkout_complete:
        st.success("Order placed successfully.")
    elif st.button(
        "Place order",
        type="primary",
        icon=":material/check_circle:",
    ):
        try:
            result = create_order(
                user_id,
                address_labels[selected_address],
                payment_method,
                coupon_code,
            )
        except (PermissionError, ValueError, OSError, sqlite3.Error) as error:
            st.error(str(error))
        else:
            st.session_state.cart = {}
            st.session_state.demo_checkout_complete = True
            st.success(f"Order #{result['order_id']} placed successfully.")
            st.rerun()

    if st.button("Return to cart", icon=":material/arrow_back:"):
        st.session_state.store_page = "cart"
        st.rerun()
