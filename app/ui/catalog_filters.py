import streamlit as st


def reset_catalog_page() -> None:
    st.session_state["catalog_page"] = 1


def reset_catalog_filters() -> None:
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
    ):
        st.session_state.pop(key, None)
    reset_catalog_page()
    st.session_state["catalog_view"] = False


def sync_category_from_nav() -> None:
    st.session_state["category_select"] = st.session_state.get(
        "category_nav", "All Categories"
    )
    reset_catalog_page()
    st.session_state["catalog_view"] = True


def sync_category_from_sidebar() -> None:
    st.session_state["category_nav"] = st.session_state.get(
        "category_select", "All Categories"
    )
    reset_catalog_page()
    st.session_state["catalog_view"] = True


def sync_product_layout_preference() -> None:
    st.session_state["catalog_layout_preference"] = st.session_state.get(
        "product_view", "Grid"
    )
