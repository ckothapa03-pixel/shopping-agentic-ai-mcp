import sqlite3
from decimal import Decimal

import streamlit as st

from app.shopping.cart import cart_total, remove_from_cart, update_cart_quantity
from app.ui.catalog import _load_cart_products

def _render_cart() -> None:
    st.header("Your shopping cart")
    st.caption(
        "This cart is temporary to the current browser session; it is not saved "
        "to an account."
    )

    if not st.session_state.cart:
        st.info("Your cart is empty. Add something you like from the catalog.")

        if st.button("Continue shopping", icon=":material/storefront:"):
            st.session_state.store_page = "shop"
            st.rerun()
        return

    products_by_id = _load_cart_products()
    if products_by_id is None:
        return

    for product_id, quantity in list(st.session_state.cart.items()):
        product = products_by_id.get(product_id)

        if product is None:
            st.warning("A cart item is no longer in the catalog.")

            if st.button("Remove unavailable item", key=f"remove-missing-{product_id}"):
                st.session_state.cart = remove_from_cart(
                    st.session_state.cart, product_id
                )
                st.rerun()
            continue

        with st.container(border=True, key=f"cart-line-{product_id}"):
            item_columns = st.columns([3, 1.2, 1, 1], vertical_alignment="center")
            item_columns[0].markdown(f"**{product['name']}**")
            item_columns[0].caption(
                f"₹{product['price']:,.2f} each · "
                f"{product.get('brand') or '—'}"
            )

            if product["stock"] < 1:
                item_columns[1].warning("Out of stock")
                item_columns[2].caption("Unavailable")
            else:
                quantity_key = f"cart-quantity-{product_id}"
                stock_limit = int(product["stock"])

                if st.session_state.get(quantity_key, quantity) > stock_limit:
                    st.session_state.pop(quantity_key, None)

                selected_quantity = item_columns[1].number_input(
                    "Quantity",
                    min_value=1,
                    max_value=stock_limit,
                    value=min(quantity, stock_limit),
                    key=quantity_key,
                )

                if item_columns[2].button(
                    "Update",
                    key=f"update-cart-{product_id}",
                ):
                    try:
                        st.session_state.cart = update_cart_quantity(
                            st.session_state.cart,
                            product,
                            selected_quantity,
                        )
                        st.session_state.demo_checkout_complete = False
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))

            if item_columns[3].button(
                "Remove",
                key=f"remove-cart-{product_id}",
            ):
                st.session_state.cart = remove_from_cart(
                    st.session_state.cart, product_id
                )
                st.session_state.demo_checkout_complete = False
                st.rerun()

            if product["stock"] > 0 and quantity <= product["stock"]:
                line_total = Decimal(str(product["price"])) * quantity
                st.caption(f"Line total: ₹{line_total:,.2f}")
            elif product["stock"] > 0:
                st.warning(
                    f"Requested quantity {quantity} exceeds current stock "
                    f"({product['stock']}). Update the quantity before checkout."
                )

    try:
        total = cart_total(st.session_state.cart, products_by_id)
    except (KeyError, ValueError):
        st.warning("Update or remove unavailable items to recalculate your total.")
    else:
        st.markdown(f"### Cart total: ₹{total:,.2f}")
        st.caption("Totals are recalculated from current catalog prices.")
        action_columns = st.columns([1, 1, 3])

        if action_columns[0].button(
            "Checkout",
            icon=":material/lock:",
            type="primary",
            width="stretch",
        ):
            st.session_state.store_page = "checkout"
            st.session_state.demo_checkout_complete = False
            st.rerun()

        if action_columns[1].button("Clear cart", width="stretch"):
            st.session_state.cart = {}
            st.session_state.demo_checkout_complete = False
            st.rerun()
