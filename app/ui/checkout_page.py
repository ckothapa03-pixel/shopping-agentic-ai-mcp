from decimal import Decimal

import streamlit as st

from app.shopping.cart import validate_checkout
from app.ui.catalog import _load_cart_products

def _render_demo_checkout() -> None:
    st.header("Demo checkout")
    st.warning(
        "This is a demonstration only. No payment is taken and no order is saved."
    )

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

    if st.session_state.demo_checkout_complete:
        st.success("Demo checkout complete. No order was placed or stored.")
    elif st.button(
        "Complete demo checkout",
        type="primary",
        icon=":material/check_circle:",
    ):
        st.session_state.demo_checkout_complete = True
        st.rerun()

    if st.button("Return to cart", icon=":material/arrow_back:"):
        st.session_state.store_page = "cart"
        st.rerun()
