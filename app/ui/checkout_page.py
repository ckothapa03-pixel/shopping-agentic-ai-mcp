import sqlite3

from decimal import Decimal

import streamlit as st

from app.shopping.cart import validate_checkout
from app.ui.catalog import _load_cart_products
from app.db.address_repository import list_addresses
from app.db.checkout_repository import calculate_coupon_discount, create_order
from app.db.user_data import get_cart
from app.shopping.identity import require_authenticated_user
from app.shopping.money import money
from app.shopping.confirmation import (
    confirmation_matches,
    consume_confirmation,
    request_confirmation,
)
from app.ui.error_messages import safe_error_message

def _render_demo_checkout() -> None:
    st.header("Checkout")
    if st.session_state.access_mode != "authenticated":
        st.error("Sign in to place an order.")
        return
    try:
        user_id = require_authenticated_user(st.session_state)
        addresses = list_addresses(user_id)
    except (PermissionError, OSError, sqlite3.Error) as error:
        st.error(safe_error_message(error, "Checkout information could not be loaded.", event="checkout_load_failed"))
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
        unit_price = money(product["price"])
        line_total = money(unit_price * quantity)
        st.write(
            f"{product['name']} · {quantity} × ₹{unit_price:,.2f} "
            f"= ₹{line_total:,.2f}"
        )

    st.markdown(f"### Subtotal: ₹{total:,.2f}")

    address_labels = {
        f"{address['label']} - {address['line1']}, {address['city']}": address["id"]
        for address in addresses
    }
    selected_address = st.selectbox("Delivery address", list(address_labels))
    payment_method = st.selectbox("Payment method", ["COD"])
    coupon_code = st.text_input("Coupon code").strip() or None

    try:
        stored_cart = get_cart(user_id)
    except (PermissionError, OSError, sqlite3.Error) as error:
        st.error(safe_error_message(error, "Your saved cart could not be checked.", event="checkout_cart_check_failed"))
        return
    stored_quantities = {
        int(row["product_id"]): int(row["quantity"])
        for row in stored_cart
        if row["product"] is not None
    }
    visible_quantities = {
        int(product_id): int(quantity)
        for product_id, quantity in st.session_state.cart.items()
    }
    if stored_quantities != visible_quantities or len(stored_cart) != len(stored_quantities):
        st.error("Your saved cart changed. Return to your cart and review it again.")
        return
    try:
        discount = calculate_coupon_discount(money(total), coupon_code)
    except (ValueError, OSError, sqlite3.Error) as error:
        st.error(safe_error_message(error, "The coupon could not be validated.", event="coupon_validation_failed", allow_value_error=True))
        return
    checkout_total = money(Decimal(str(total)) - discount)
    st.caption(f"Coupon discount: −₹{discount:,.2f}")
    st.markdown(f"### Total: ₹{checkout_total:,.2f}")
    expected_cart = sorted(
        (
            int(row["product_id"]),
            int(row["quantity"]),
            str(money(row["product"]["price"])),
        )
        for row in stored_cart
    )
    address_id = address_labels[selected_address]
    confirmation_parameters = {
        "address_id": address_id,
        "payment_method": payment_method,
        "coupon_code": coupon_code,
        "cart": expected_cart,
        "total": str(checkout_total),
    }
    confirmation_key = "pending_checkout_confirmation"
    is_confirming = confirmation_matches(
        st.session_state,
        confirmation_key,
        "create_checkout_order",
        user_id,
        confirmation_parameters,
    )

    if st.session_state.demo_checkout_complete:
        st.success("Order placed successfully.")
    elif is_confirming:
        st.warning("Review the order summary above, then confirm this order.")
        if st.button(
            f"Confirm order · ₹{checkout_total:,.2f}",
            type="primary",
            icon=":material/check_circle:",
        ):
            approved = consume_confirmation(
                st.session_state,
                confirmation_key,
                "create_checkout_order",
                user_id,
                confirmation_parameters,
            )
            if not approved:
                st.error("Checkout confirmation expired. Review the order again.")
            else:
                try:
                    result = create_order(
                        user_id,
                        address_id,
                        payment_method,
                        coupon_code,
                        expected_cart=expected_cart,
                        expected_total=checkout_total,
                    )
                except (PermissionError, ValueError, OSError, sqlite3.Error) as error:
                    st.error(safe_error_message(error, "The order could not be placed. Review your cart and try again.", event="order_creation_failed", allow_value_error=True))
                else:
                    st.session_state.cart = {}
                    st.session_state.demo_checkout_complete = True
                    st.success(f"Order #{result['order_id']} placed successfully.")
                    st.rerun()
        if st.button("Review again", key="review-checkout-again"):
            st.session_state.pop(confirmation_key, None)
            st.rerun()
    elif st.button("Review and place order", type="primary"):
        request_confirmation(
            st.session_state,
            confirmation_key,
            "create_checkout_order",
            user_id,
            confirmation_parameters,
        )
        st.rerun()

    if st.button("Return to cart", icon=":material/arrow_back:"):
        st.session_state.store_page = "cart"
        st.rerun()
