import html
from typing import Any

import streamlit as st

def _render_chat_product(product: dict[str, Any]) -> None:
    """Render product facts supplied by the database-backed MCP search."""
    name = html.escape(str(product.get("name") or "Catalog product"))
    price = product.get("price")

    price_text = (
        f"₹{price:,.2f}"
        if isinstance(price, (int, float))
        else "Price unavailable"
    )

    rating = product.get("rating_avg")
    rating_text = (
        f"{rating:.1f}/5"
        if isinstance(rating, (int, float))
        else "Not rated"
    )

    stock = product.get("stock")
    stock_text = (
        f"In stock ({stock})"
        if isinstance(stock, (int, float)) and stock > 0
        else "Out of stock"
    )

    with st.container(border=True, key=f"chat-product-{product.get('id', name)}"):
        st.markdown(
            '<div class="product-image-placeholder" role="img" '
            f'aria-label="Image of {name} unavailable">'
            '<span aria-hidden="true">Product image unavailable</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(f"**{name}**")
        st.markdown(f"**{price_text}** · ★ {rating_text}")
        st.caption(
            f"{stock_text} · {product.get('brand') or '—'} · "
            f"{product.get('category') or '—'}"
        )
