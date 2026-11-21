import sqlite3
from pathlib import Path

import streamlit as st

from app.ui.catalog_data import load_featured_products
from app.ui.product_card import _render_product

PROJECT_ROOT = Path(__file__).resolve().parents[2]

HERO_IMAGE_PATH = PROJECT_ROOT / "assets" / "hero" / "shopwise-hero-still-life.png"

CATEGORY_ICONS = (
    ("audio", "headphones"),
    ("cable", "cable"),
    ("charger", "cable"),
    ("gaming", "sports_esports"),
    ("laptop", "laptop_mac"),
    ("keyboard", "keyboard"),
    ("mouse", "mouse"),
    ("monitor", "desktop_windows"),
    ("network", "router"),
    ("smart home", "home_iot_device"),
    ("storage", "database"),
    ("wearable", "watch"),
    ("mobile", "devices"),
)

CATEGORY_IMAGES = {
    "Audio": "headphones.svg",
    "Cables & Chargers": "cables.svg",
    "Gaming": "gaming.svg",
    "Laptop Accessories": "laptop.svg",
    "Mice & Keyboards": "mice-keyboard.svg",
    "Monitors & Displays": "monitor.svg",
    "Networking": "networking.svg",
    "Smart Home": "smart-home.svg",
    "Storage": "storage.svg",
    "Wearables & Mobile": "wearable.svg",
}

def _category_image(category: str) -> Path | None:
    for label, filename in CATEGORY_IMAGES.items():
        if category.casefold() == label.casefold():
            path = PROJECT_ROOT / "assets" / "images" / "categories" / filename
            return path if path.is_file() else None
    return None

def _category_icon(category: str) -> str:
    normalized = category.casefold()
    return next(
        (icon for word, icon in CATEGORY_ICONS if word in normalized),
        "category",
    )

def _select_catalog_category(category: str) -> None:
    st.session_state["category_nav"] = category
    st.session_state["category_select"] = category
    st.session_state["catalog_page"] = 1
    st.session_state["catalog_view"] = True

def _open_catalog() -> None:
    st.session_state["catalog_view"] = True
    st.session_state["catalog_page"] = 1

def _render_home_hero() -> None:
    with st.container(key="home-hero"):
        copy, visual = st.columns([1, 1.2], vertical_alignment="center")
        with copy:
            st.caption("SHOPWISE · YOUR TECH & LIFESTYLE STORE")
            st.markdown("# Discover a Smarter Way to Shop")
            st.write(
                "Explore top brands, latest gadgets and everyday essentials "
                "all in one place."
            )
            st.button(
                "Shop now",
                key="hero-shop-now",
                icon=":material/arrow_forward:",
                type="primary",
                on_click=_open_catalog,
            )
            st.markdown(
                '<div class="hero-trust-row">'
                '<span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h11v9H3zm11 4h4l3 3v2h-7zM6.5 18a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm10 0a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/></svg><b>Fast Delivery</b><small>Across India</small></span>'
                '<span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l7 3v5c0 5-3 9-7 12-4-3-7-7-7-12V5zm0 3v13c2.5-2.2 4-4.8 4-8V7z"/></svg><b>Secure Shopping</b><small>100% Safe &amp; Trusted</small></span>'
                '<span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7V3l-4 4 4 4V8h8a4 4 0 0 1 4 4v1h2v-1a6 6 0 0 0-6-6zm10 10v4l4-4-4-4v3H9a4 4 0 0 1-4-4v-1H3v1a6 6 0 0 0 6 6z"/></svg><b>Easy Returns</b><small>Hassle-Free</small></span>'
                '<span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 13v-2a8 8 0 0 1 16 0v2h-2v-2a6 6 0 0 0-12 0v2zm-2 1h4v6H2zm16 0h4v6h-4zm-7 5h6v2H11z"/></svg><b>24x7 Support</b><small>We are here for you</small></span>'
                '</div>',
                unsafe_allow_html=True,
            )
        with visual:
            st.image(
                str(HERO_IMAGE_PATH),
                alt="Decorative still-life of a laptop, headphones, router, light bulb, and plant",
                width="stretch",
            )

def _render_home_categories(categories: list[str]) -> None:
    with st.container(key="home-category-heading"):
        heading, view_all = st.columns([4, 1], vertical_alignment="center")
        with heading:
            st.subheader("Shop by Category")
        with view_all:
            st.button(
                "View all categories",
                key="view-all-categories",
                icon=":material/arrow_forward:",
                on_click=_open_catalog,
                width="stretch",
            )
    with st.container(key="home-category-grid"):
        cards_per_row = 10 if len(categories) <= 10 else 5
        for row_start in range(0, len(categories), cards_per_row):
            row_categories = categories[row_start : row_start + cards_per_row]
            columns = st.columns(cards_per_row, gap="small", vertical_alignment="center")
            for index, (column, category) in enumerate(
                zip(columns, row_categories), start=row_start
            ):
                with column:
                    with st.container(
                        border=True,
                        key=f"home-category-card-{index}",
                    ):
                        image_path = _category_image(category)
                        if image_path is not None:
                            st.image(str(image_path), width="content")
                        else:
                            st.markdown(f":material/{_category_icon(category)}:")
                        st.button(
                            category,
                            key=f"home-category-select-{index}",
                            width="stretch",
                            on_click=_select_catalog_category,
                            args=(category,),
                        )

def _render_homepage(categories: list[str]) -> None:
    _render_home_hero()
    if st.session_state.access_mode == "authenticated":
        st.caption(
            f"Welcome, {st.session_state.get('authenticated_name', 'Shopper')}"
        )
    _render_home_categories(categories)

    with st.container(key="featured-products-heading"):
        heading, view_all = st.columns([4, 1], vertical_alignment="center")
        with heading:
            st.subheader("Featured Products")
        with view_all:
            st.button(
                "View all products",
                key="view-all-products",
                icon=":material/arrow_forward:",
                on_click=_open_catalog,
                width="stretch",
            )
    try:
        featured_products = load_featured_products()
    except (OSError, sqlite3.Error, ValueError):
        st.error("Featured products could not be loaded. Please try again.")
        return
    if not featured_products:
        st.info("There are no products to feature yet.")
    else:
        with st.container(key="featured-product-grid"):
            columns = st.columns(6, gap="medium")
            for column, product in zip(columns, featured_products):
                with column:
                    _render_product(product, grid_view=True, featured=True)
