import html
import sqlite3
from typing import Any

import streamlit as st

from app.shopping.cart import add_to_cart
from app.db.products import get_products_by_ids
from app.db.user_data import (
    set_cart_quantity,
    set_wishlist as persist_wishlist,
)
from app.ui.product_images import get_product_image_path
from app.ui.product_card_cart import render_cart_quantity_controls

__all__ = ["_render_product"]

def _render_cart_quantity_controls(product: dict[str, Any]) -> bool:
    return render_cart_quantity_controls(product)



def _render_product(
    product: dict[str, Any],
    *,
    grid_view: bool,
    featured: bool = False,
) -> None:
    product_id = product["id"]
    stock = product["stock"]
    is_saved = product_id in st.session_state.wishlist
    accessible_name = html.escape(
        str(product.get("name") or "Catalog product"),
        quote=True,
    )
    category = html.escape(str(product.get("category") or "Shopwise catalog"), quote=True)
    with st.container(border=True, key=f"product-card-{product_id}"):
        image_path = get_product_image_path(product)
        if image_path is not None:
            st.image(
                str(image_path),
                caption=None,
                width="stretch",
            )
        else:
            st.markdown(
                '<div class="'
                f'product-image-fallback{" featured-product-image" if featured else ""}'
                '" role="img" '
                f'aria-label="Category illustration for {accessible_name}">'
                '<span class="product-fallback-icon" aria-hidden="true">'
                '<span class="product-fallback-box"></span>'
                '</span>'
                f'<span class="product-fallback-category">{category}</span>'
                '</div>',
                unsafe_allow_html=True,
            )
        wishlist_button = False
        if featured:
            wishlist_button = st.button(
                "Saved" if is_saved else "Save",
                key=f"wishlist-product-{product_id}",
                icon=":material/favorite:" if is_saved else ":material/favorite_border:",
                help="Remove from wishlist" if is_saved else "Save to wishlist",
                width="content",
            )
        if grid_view:
            if featured:
                st.markdown(
                    '<div class="featured-product-name">'
                    f"{html.escape(str(product['name']))}</div>",
                    unsafe_allow_html=True,
                )
                rating, availability = st.columns(
                    [1, 1],
                    vertical_alignment="center",
                )
                if product["rating_count"] > 0:
                    rating.caption(f":material/star: {product['rating_avg']:.1f}")
                else:
                    rating.caption("Not rated")
                availability.caption(
                    f"In stock ({stock})" if stock > 0 else "Out of stock"
                )
                st.markdown(f"### ₹{product['price']:,.2f}")
            else:
                st.markdown(
                    '<div class="product-card-title">'
                    f"{html.escape(str(product['name']))}"
                    "</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"### ₹{product['price']:,.2f}")
                st.caption(
                    f"{product.get('brand') or '—'} · "
                    f"{product.get('category') or '—'}"
                )
        else:
            details, actions = st.columns([3, 1], vertical_alignment="center")
            with details:
                st.markdown(
                    '<div class="product-card-title">'
                    f"{html.escape(str(product['name']))}"
                    "</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"### ₹{product['price']:,.2f}")
                st.caption(
                    f"{product.get('brand') or '—'} · "
                    f"{product.get('category') or '—'}"
                )

        if not featured:
            if product["rating_count"] > 0:
                st.write(
                    f":material/star: {product['rating_avg']:.1f}/5 · "
                    f"{product['rating_count']} reviews"
                )
            else:
                st.caption("No customer ratings yet")
            if stock > 0:
                st.caption(f"In stock · {stock} available")
            else:
                st.caption("Currently out of stock")

            with st.expander("Product details"):
                st.write(product["description"] or "No description available.")
                st.caption(f"SKU: {product['sku']} · MRP: ₹{product['mrp']:,.2f}")

        if grid_view:
            if featured:
                quantity_control_rendered = _render_cart_quantity_controls(product)
                if quantity_control_rendered:
                    add_button = False
                else:
                    add_button = st.button(
                        "Add to cart",
                        key=f"add-product-{product_id}",
                        disabled=stock < 1,
                        type="primary",
                        width="stretch",
                    )
            else:
                action_columns = st.columns([1.3, 1], vertical_alignment="center")
                quantity_control_rendered = _render_cart_quantity_controls(product)
                if quantity_control_rendered:
                    add_button = False
                else:
                    add_button = action_columns[0].button(
                        "Add to cart",
                        key=f"add-product-{product_id}",
                        disabled=stock < 1,
                        type="primary",
                        width="stretch",
                    )
                wishlist_button = action_columns[1].button(
                    "Saved" if is_saved else "Save",
                    key=f"wishlist-product-{product_id}",
                    icon=":material/favorite:" if is_saved else ":material/favorite_border:",
                    help="Remove from wishlist" if is_saved else "Save to wishlist",
                    width="stretch",
                )
        else:
            quantity_control_rendered = _render_cart_quantity_controls(product)
            add_button = False
            if not quantity_control_rendered:
                add_button = actions.button(
                    "Add to cart",
                    key=f"add-product-{product_id}",
                    disabled=stock < 1,
                    type="primary",
                    width="stretch",
                )
            wishlist_button = actions.button(
                "Saved" if is_saved else "Save to wishlist",
                key=f"wishlist-product-{product_id}",
                icon=":material/favorite:" if is_saved else ":material/favorite_border:",
                width="stretch",
            )

        if add_button:
            try:
                current_products = get_products_by_ids([product_id])
                if not current_products:
                    raise ValueError("This product is no longer available.")
                st.session_state.cart = add_to_cart(
                    st.session_state.cart,
                    current_products[0],
                )
                if st.session_state.access_mode == "authenticated":
                    persist_user_id = st.session_state.get("authenticated_user_id")
                    if persist_user_id:
                            try:
                                set_cart_quantity(
                                    persist_user_id,
                                    product_id,
                                    st.session_state.cart[product_id],
                                )
                            except (PermissionError, ValueError, OSError, sqlite3.Error):
                                pass
                st.session_state.demo_checkout_complete = False
                st.toast(f"Added {product['name']} to your cart.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))
            except (OSError, sqlite3.Error):
                st.error("The current product availability could not be checked.")
        if wishlist_button:
            if is_saved:
                st.session_state.wishlist.discard(product_id)
                saved = False
                st.toast("Removed from your session wishlist.")
            else:
                st.session_state.wishlist.add(product_id)
                saved = True
                st.toast("Added to your session wishlist.")
            if st.session_state.access_mode == "authenticated":
                persist_user_id = st.session_state.get("authenticated_user_id")
                if persist_user_id:
                    try:
                        persist_wishlist(persist_user_id, product_id, saved)
                    except (PermissionError, ValueError, OSError, sqlite3.Error):
                        pass
            st.rerun()
