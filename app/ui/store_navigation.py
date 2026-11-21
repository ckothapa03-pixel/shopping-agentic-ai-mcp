import streamlit as st
from app.ui import catalog as catalog_ui
from app.shopping.identity import (
    clear_authenticated_session,
    prepare_login_session,
)

def _return_to_homepage() -> None:
    st.session_state.store_page = "shop"
    catalog_ui._reset_catalog_filters()
    st.session_state.catalog_page = 1

def _start_login() -> None:
    prepare_login_session(st.session_state)
    st.session_state.auth_view = "login"

def _logout_to_guest() -> None:
    clear_authenticated_session(st.session_state)
    st.session_state.pop("auth_notice", None)
    st.session_state.auth_view = "login"
    st.session_state.store_page = "shop"

def _render_store_header() -> None:
    cart_count = sum(st.session_state.cart.values())
    wishlist_count = len(st.session_state.wishlist)

    with st.container(key="store-header"):
        with st.container(key="store-header-row"):
            header = st.columns([150, 1, 330], gap="small", vertical_alignment="center")

            with header[0]:
                st.button(
                    "Shopwise",
                    key="home-logo",
                    icon=":material/shopping_cart:",
                    help="Return to the Shopwise homepage",
                    on_click=_return_to_homepage,
                    type="tertiary",
                )

            with header[1]:
                with st.form(key="catalog-search-form", border=False):
                    search_columns = st.columns(
                        [1, 112],
                        vertical_alignment="center",
                    )
                    query = search_columns[0].text_input(
                        "Search the catalog",
                        placeholder="Search for products, brands, or categories...",
                        key="catalog_search_input",
                        label_visibility="collapsed",
                    )
                    submitted = search_columns[1].form_submit_button(
                        "Search",
                        icon=":material/search:",
                        type="primary",
                        width="stretch",
                    )

                if submitted:
                    st.session_state.catalog_search_query = query.strip()
                    st.session_state.catalog_view = True
                    st.session_state.store_page = "shop"
                    st.session_state.catalog_page = 1

            with header[2]:
                actions = st.columns(
                    [1, 1, 1],
                    vertical_alignment="center",
                )
                account_action = actions[0].menu_button(
                    "Account",
                    options=(
                        ["Profile", "Settings", "Addresses", "Orders", "Logout"]
                        if st.session_state.access_mode == "authenticated"
                        else ["Login"]
                    ),
                    key="account-menu",
                    icon=":material/person:",
                    help="Account and sign-in options",
                    width="stretch",
                )

                with actions[1]:
                    with st.container(key="wishlist-header-action"):
                        wishlist_clicked = st.button(
                            "Wishlist",
                            key="open-wishlist",
                            icon=":material/favorite:",
                            help=f"Open wishlist · {wishlist_count} saved products",
                            width="stretch",
                        )
                        if wishlist_count > 0:
                            st.markdown(
                                '<span class="store-count-badge" '
                                f'aria-label="{wishlist_count} saved products">'
                                f"{wishlist_count}</span>",
                                unsafe_allow_html=True,
                            )

                if wishlist_clicked:
                    st.session_state.store_page = "wishlist"

                with actions[2]:
                    with st.container(key="cart-header-action"):
                        cart_clicked = st.button(
                            "Cart",
                            key="open-cart",
                            icon=":material/shopping_cart:",
                            help=f"Open cart · {cart_count} items",
                            width="stretch",
                        )
                        if cart_count > 0:
                            st.markdown(
                                '<span class="store-count-badge" '
                                f'aria-label="{cart_count} cart items">'
                                f"{cart_count}</span>",
                                unsafe_allow_html=True,
                            )

                if cart_clicked:
                    st.session_state.store_page = "cart"

                if account_action == "Profile":
                    st.session_state.store_page = "profile"
                    st.rerun()

                if account_action == "Settings":
                    st.session_state.store_page = "settings"
                    st.rerun()

                if account_action == "Addresses":
                    st.session_state.store_page = "addresses"
                    st.rerun()

                if account_action == "Orders":
                    st.session_state.store_page = "orders"
                    st.rerun()

                if account_action == "Login":
                    _start_login()
                    st.rerun()

                if account_action == "Logout":
                    _logout_to_guest()
                    st.rerun()
