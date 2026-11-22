import sqlite3
import streamlit as st

from app.db.products import get_products_by_ids
from app.ui.error_messages import safe_error_message


def _render_comparison() -> None:
    st.header("Compare products")
    raw = st.text_input(
        "Product IDs (comma-separated)",
        help="Find a product ID by expanding Product details on a catalog card.",
    )
    if not raw:
        st.info("Enter 2 to 4 product IDs.")
        return
    try:
        ids = [int(value.strip()) for value in raw.split(",") if value.strip()]
        if len(ids) not in range(2, 5) or len(set(ids)) != len(ids):
            raise ValueError("Enter 2 to 4 unique product IDs.")
        products = get_products_by_ids(ids)
    except (ValueError, OSError, sqlite3.Error) as error:
        st.error(safe_error_message(error, "Products could not be compared.", event="comparison_load_failed", allow_value_error=True))
        return
    if len(products) != len(ids):
        st.error("One or more products could not be found.")
        return
    rows = [
        {
            "Name": product["name"],
            "Brand": product["brand"] or "-",
            "Category": product["category"] or "-",
            "Price": f"₹{product['price']:,.2f}",
            "MRP": f"₹{product['mrp']:,.2f}",
            "Rating": f"{product['rating_avg']:.1f}",
            "Reviews": product["rating_count"],
            "Stock": product["stock"],
            "Availability": "In stock" if product["stock"] > 0 else "Out of stock",
        }
        for product in products
    ]
    st.dataframe(rows, use_container_width=True)
