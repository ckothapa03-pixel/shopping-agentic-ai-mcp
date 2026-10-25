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
        for row_start in range(0, len(categories), 5):
            row_categories = categories[row_start : row_start + 5]
            columns = st.columns(5, gap="small", vertical_alignment="center")
            for index, (column, category) in enumerate(
                zip(columns, row_categories), start=row_start
            ):
                with column:
                    with st.container(
                        border=True,
                        key=f"home-category-card-{index}",
                    ):
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
            columns = st.columns(6, gap="small")
            for column, product in zip(columns, featured_products):
                with column:
                    _render_product(product, grid_view=True, featured=True)
