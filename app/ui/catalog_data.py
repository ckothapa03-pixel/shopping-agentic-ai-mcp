from typing import Any

import streamlit as st

from app.db.products import count_products, find_products, get_catalog_facets, get_catalog_price_bounds

PRODUCTS_PER_PAGE = 15

@st.cache_data(ttl=15)
def browse_catalog(
    search_term: str,
    min_price: float,
    max_price: float,
    min_rating: float,
    in_stock: bool,
    category: str | None,
    brand: str | None,
    sort_by: str,
    page: int,
) -> tuple[list[dict[str, Any]], int]:
    filters = {
        "search_term": search_term,
        "min_price": min_price,
        "max_price": max_price,
        "min_rating": min_rating,
        "in_stock": in_stock,
        "category": category,
        "brand": brand,
    }
    total = count_products(**filters)
    products = find_products(
        search_term=search_term,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        in_stock=in_stock,
        category=category,
        brand=brand,
        sort_by=sort_by,
        limit=PRODUCTS_PER_PAGE,
        offset=(page - 1) * PRODUCTS_PER_PAGE,
    )
    return products, total

@st.cache_data(ttl=60)
def load_catalog_facets() -> dict[str, list[str]]:
    return get_catalog_facets()

@st.cache_data(ttl=60)
def load_catalog_price_bounds() -> tuple[float, float] | None:
    return get_catalog_price_bounds()

@st.cache_data(ttl=60)
def load_featured_products() -> list[dict[str, Any]]:
    """Return a small selection of actual catalog products for the home page."""
    return find_products(sort_by="highest_rated", limit=6)
