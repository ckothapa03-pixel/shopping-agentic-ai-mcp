import sqlite3
from typing import Any

import streamlit as st

from app.shopping.cart import cart_total
from app.db.products import get_products_by_ids
from app.ui.catalog_data import (
    PRODUCTS_PER_PAGE,
    browse_catalog,
    load_catalog_facets,
    load_catalog_price_bounds,
)
from app.ui.catalog_home import _render_homepage
from app.ui.product_card import _render_product

__all__ = [
    "PRODUCTS_PER_PAGE",
    "_load_cart_products",
    "_render_page_controls",
    "_render_product",
    "_render_shop",
    "_reset_catalog_filters",
    "_sync_category_from_nav",
    "browse_catalog",
    "load_catalog_facets",
    "load_catalog_price_bounds",
    "load_featured_products",
]

def _reset_catalog_page() -> None:
    st.session_state["catalog_page"] = 1

def _reset_catalog_filters() -> None:
    for key in (
        "catalog_search_input",
        "catalog_search_query",
        "category_nav",
        "category_select",
        "brand_select",
        "min_price_filter",
        "max_price_filter",
        "rating_filter",
        "stock_filter",
        "sort_filter",
        "product_view",
        "catalog_search_query",
    ):
        st.session_state.pop(key, None)
    _reset_catalog_page()
    st.session_state["catalog_view"] = False

def _clear_catalog_search() -> None:
    st.session_state["catalog_search_query"] = ""
    st.session_state["catalog_search_input"] = ""
    _reset_catalog_page()
    default_max = st.session_state.get("catalog_price_ceiling", float("inf"))
    st.session_state["catalog_view"] = any(
        (
            st.session_state.get("category_select", "All Categories")
            != "All Categories",
            st.session_state.get("brand_select", "All Brands") != "All Brands",
            st.session_state.get("min_price_filter", 0.0) > 0,
            st.session_state.get("max_price_filter", default_max) < default_max,
            st.session_state.get("rating_filter", 0.0) > 0,
            st.session_state.get("stock_filter", False),
            st.session_state.get("sort_filter", "Relevance") != "Relevance",
        )
    )

def _sync_category_from_nav() -> None:
    st.session_state["category_select"] = st.session_state.get(
        "category_nav", "All Categories"
    )
    _reset_catalog_page()
    st.session_state["catalog_view"] = True

def _sync_category_from_sidebar() -> None:
    st.session_state["category_nav"] = st.session_state.get(
        "category_select", "All Categories"
    )
    _reset_catalog_page()
    st.session_state["catalog_view"] = True

def _sync_product_layout_preference() -> None:
    st.session_state["catalog_layout_preference"] = st.session_state.get(
        "product_view", "Grid"
    )

def _load_cart_products() -> dict[int, dict[str, Any]] | None:
    try:
        rows = get_products_by_ids(list(st.session_state.cart))
    except (OSError, sqlite3.Error, ValueError):
        st.error("The current catalog could not be checked. Please retry.")
        return None
    return {product["id"]: product for product in rows}

def _render_page_controls(
    current_page: int,
    total_pages: int,
    *,
    key_prefix: str,
) -> None:
    if total_pages <= 1:
        return

    first_page = max(1, min(current_page - 2, total_pages - 4))
    page_numbers = range(first_page, min(total_pages, first_page + 4) + 1)
    controls = st.columns(len(page_numbers) + 2, vertical_alignment="center")
    if controls[0].button(
        "Previous",
        key=f"{key_prefix}-previous",
        disabled=current_page == 1,
        width="stretch",
    ):
        st.session_state.catalog_page = current_page - 1
        st.rerun()

    for column, page_number in zip(controls[1:-1], page_numbers):
        if column.button(
            str(page_number),
            key=f"{key_prefix}-page-{page_number}",
            type="primary" if page_number == current_page else "secondary",
            width="stretch",
        ):
            st.session_state.catalog_page = page_number
            st.rerun()

    if controls[-1].button(
        "Next",
        key=f"{key_prefix}-next",
        disabled=current_page == total_pages,
        width="stretch",
    ):
        st.session_state.catalog_page = current_page + 1
        st.rerun()
    st.caption(f"Page {current_page} of {total_pages}")

def _render_shop(facets: dict[str, list[str]]) -> None:
    active_search = st.session_state.get("catalog_search_query", "").strip()
    is_catalog_view = st.session_state.get("catalog_view", False) or bool(active_search)
    if not is_catalog_view:
        _render_homepage(facets["categories"])
        return

    if st.session_state.access_mode == "authenticated":
        st.subheader(
            f"Welcome, {st.session_state.get('authenticated_name', 'Shopper')}"
        )
    else:
        st.caption("Browsing as a guest · cart and wishlist are temporary to this session")

    try:
        price_bounds = load_catalog_price_bounds()
    except (OSError, sqlite3.Error, ValueError):
        st.error("The product catalog could not be loaded. Please try again.")
        return
    if price_bounds is None:
        st.info("The catalog is empty.")
        return

    _, largest_price = price_bounds
    st.session_state["catalog_price_ceiling"] = largest_price
    with st.sidebar:
        st.subheader("Filter products")
        st.selectbox(
            "Category",
            ["All Categories", *facets["categories"]],
            key="category_select",
            on_change=_sync_category_from_sidebar,
        )
        st.selectbox(
            "Brand",
            ["All Brands", *facets["brands"]],
            key="brand_select",
            on_change=_reset_catalog_page,
        )
        st.number_input(
            "Minimum price (₹)",
            min_value=0.0,
            max_value=largest_price,
            value=0.0,
            step=100.0,
            key="min_price_filter",
            on_change=_reset_catalog_page,
        )
        st.number_input(
            "Maximum price (₹)",
            min_value=0.0,
            max_value=largest_price,
            value=largest_price,
            step=100.0,
            key="max_price_filter",
            on_change=_reset_catalog_page,
        )
        st.slider(
            "Minimum customer rating",
            min_value=0.0,
            max_value=5.0,
            value=0.0,
            step=0.5,
            key="rating_filter",
            on_change=_reset_catalog_page,
        )
        st.checkbox(
            "In stock only",
            key="stock_filter",
            on_change=_reset_catalog_page,
        )
        st.selectbox(
            "Sort by",
            options=[
                "Relevance",
                "Price: low to high",
                "Price: high to low",
                "Highest rated",
                "Product name: A–Z",
            ],
            key="sort_filter",
            on_change=_reset_catalog_page,
        )
        st.button(
            "Clear all filters",
            key="clear-catalog-filters",
            on_click=_reset_catalog_filters,
            width="stretch",
        )
        st.caption("Filters use current catalog prices, ratings, and stock.")

    view_column, result_column = st.columns([1, 3], vertical_alignment="center")
    with view_column:
        st.segmented_control(
            "Product layout",
            options=["Grid", "List"],
            default=st.session_state.get("catalog_layout_preference", "Grid"),
            key="product_view",
            on_change=_sync_product_layout_preference,
            label_visibility="collapsed",
        )
    with result_column:
        st.caption("Browse the full catalog or narrow your selection with filters.")

    min_price = st.session_state.get("min_price_filter", 0.0)
    max_price = st.session_state.get("max_price_filter", largest_price)
    if min_price > max_price:
        st.error("Minimum price cannot be greater than maximum price.")
        return

    selected_category = st.session_state.get("category_select", "All Categories")
    selected_brand = st.session_state.get("brand_select", "All Brands")
    sort_options = {
        "Relevance": "relevance",
        "Price: low to high": "price_low_to_high",
        "Price: high to low": "price_high_to_low",
        "Highest rated": "highest_rated",
        "Product name: A–Z": "name_ascending",
    }
    filters = {
        "search_term": active_search,
        "min_price": min_price,
        "max_price": max_price,
        "min_rating": st.session_state.get("rating_filter", 0.0),
        "in_stock": st.session_state.get("stock_filter", False),
        "category": selected_category if selected_category != "All Categories" else None,
        "brand": selected_brand if selected_brand != "All Brands" else None,
        "sort_by": sort_options.get(st.session_state.get("sort_filter", "Relevance"), "relevance"),
    }
    current_page = max(1, st.session_state.get("catalog_page", 1))
    try:
        products, total_products = browse_catalog(**filters, page=current_page)
    except (OSError, sqlite3.Error, ValueError):
        st.error("Those search filters could not be applied. Check the price range.")
        return

    total_pages = (total_products + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE
    if current_page > max(1, total_pages):
        current_page = max(1, total_pages)
        st.session_state.catalog_page = current_page
        try:
            products, total_products = browse_catalog(**filters, page=current_page)
        except (OSError, sqlite3.Error, ValueError):
            st.error("Those search filters could not be applied. Check the price range.")
            return

    if active_search:
        st.header("Search results")
        st.caption(f'Search results for “{active_search}”')
        st.button(
            "Clear search",
            key="clear-catalog-search",
            on_click=_clear_catalog_search,
        )
    elif selected_category != "All Categories":
        st.header(selected_category)
    else:
        st.header("Shop all products")
    st.write(f"**{total_products} products**")
    if total_products == 0:
        st.info("No products match those filters. Try widening your search.")
        return

    grid_view = st.session_state.get("product_view", "Grid") == "Grid"
    if grid_view:
        with st.container(key="product-grid"):
            for row_start in range(0, len(products), 5):
                product_columns = st.columns(5, gap="medium")
                for column, product in zip(
                    product_columns,
                    products[row_start : row_start + 5],
                ):
                    with column:
                        _render_product(product, grid_view=True)
    else:
        for product in products:
            _render_product(product, grid_view=False)

    _render_page_controls(
        current_page,
        total_pages,
        key_prefix="catalog-bottom",
    )

    if st.session_state.cart:
        cart_products = _load_cart_products()
        if cart_products is not None:
            try:
                subtotal = cart_total(st.session_state.cart, cart_products)
            except (KeyError, ValueError):
                st.warning("Your cart needs attention before its total is available.")
            else:
                with st.container(border=True):
                    summary, action = st.columns([3, 1], vertical_alignment="center")
                    summary.markdown(f"**Cart total: ₹{subtotal:,.2f}**")
                    if action.button(
                        "View cart",
                        icon=":material/shopping_cart:",
                        width="stretch",
                    ):
                        st.session_state.store_page = "cart"
                        st.rerun()
