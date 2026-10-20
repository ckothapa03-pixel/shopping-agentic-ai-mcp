import asyncio
import os
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from google import genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.agent import respond
from app.authentication import authenticate_account, register_account
from app.cart import (
    add_to_cart,
    cart_total,
    remove_from_cart,
    update_cart_quantity,
    validate_checkout,
)
from app.db.products import find_products, get_catalog_facets, get_products_by_ids
from app.tools.products_tool import search_products

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@st.cache_data(ttl=60)
def load_catalog() -> list[dict[str, Any]]:
    return search_products(limit=1000)


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
) -> list[dict[str, Any]]:
    return find_products(
        search_term=search_term,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        in_stock=in_stock,
        category=category,
        brand=brand,
        sort_by=sort_by,
        limit=1000,
    )


@st.cache_data(ttl=60)
def load_catalog_facets() -> dict[str, list[str]]:
    return get_catalog_facets()


async def _respond_with_agent(
    user_message: str,
    conversation_history: list[dict[str, Any]],
) -> str:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Gemini is not configured. Set GEMINI_API_KEY in the project-root "
            ".env file or in your environment, then restart the app."
        )

    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server"],
        cwd=str(PROJECT_ROOT),
    )
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    async with genai.Client(api_key=api_key).aio as client:
        async with stdio_client(server_parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return await respond(
                    session=session,
                    client=client,
                    user_message=user_message,
                    model=model,
                    conversation_history=conversation_history,
                )


def _ground_chat_answer(answer: str) -> str:
    marker = "Catalog results from shopping.db:"
    if marker in answer:
        results = answer.split(marker, maxsplit=1)[1].strip()
        return f"Here are the catalog results for your request:\n\n{results}"
    if answer.strip() == "What is your maximum budget in rupees?":
        return answer
    return (
        "I couldn't verify product matches from the catalog. Try asking for "
        "a product type, rating, stock status, or maximum budget."
    )


def _render_login_screen() -> None:
    st.markdown(
        """
        <style>
        .stApp,
        .stApp [data-testid="stAppViewContainer"],
        .stApp [data-testid="stHeader"] {
            background: #f1f6fa;
            color: #14283c;
        }
        .stApp [data-testid="stMainBlockContainer"] {
            padding-top: 0.75rem;
            padding-bottom: 1rem;
        }
        .stApp [data-testid="stVerticalBlock"] {
            gap: 0.65rem;
        }
        .stApp .st-key-login-card {
            background: #ffffff;
            border: 1px solid #d7e2eb;
            border-radius: 18px;
            box-shadow: 0 14px 38px rgba(20, 40, 60, 0.09);
            padding: 1.15rem 1.35rem;
        }
        .login-intro {
            text-align: center;
            color: #334a60;
            margin: 0 0 0.35rem;
        }
        .login-intro h1 {
            color: #102a43;
            font-size: 1.45rem;
            line-height: 1.2;
            margin: 0 0 0.4rem;
        }
        .login-intro p,
        .stApp [data-testid="stMarkdownContainer"] p,
        .stApp [data-testid="stWidgetLabel"] p,
        .stApp label {
            color: #334a60;
        }
        .stApp [data-testid="stCaptionContainer"] {
            color: #52677c;
            text-align: center;
        }
        .stApp [data-testid="stTextInput"] input {
            background: #ffffff;
            border-color: #bdcbd8;
            color: #14283c;
        }
        .stApp [data-testid="stTextInput"] input:focus {
            border-color: #0f766e;
            box-shadow: 0 0 0 1px #0f766e;
        }
        .stApp [data-testid="stBaseButton-primaryFormSubmit"] {
            background: #0f766e;
            border-color: #0f766e;
            border-radius: 10px;
            color: #ffffff;
            min-height: 2.8rem;
        }
        .stApp [data-testid="stBaseButton-primaryFormSubmit"] p {
            color: #ffffff;
        }
        .stApp [data-testid="stBaseButton-primaryFormSubmit"]:hover {
            background: #115e59;
            border-color: #115e59;
            color: #ffffff;
        }
        .stApp [data-testid="stBaseButton-secondary"] {
            background: #f4f8fa;
            border: 1px solid #c7d5df;
            border-radius: 10px;
            color: #173b4f;
            min-height: 2.55rem;
        }
        .stApp [data-testid="stBaseButton-secondary"] p {
            color: #173b4f;
        }
        .stApp [data-testid="stBaseButton-secondary"]:hover {
            background: #e5f0f1;
            border-color: #7aa9aa;
            color: #102f3e;
        }
        .stApp [data-testid="stBaseButton-secondary"][kind="secondary"] {
            font-weight: 600;
        }
        .stApp [data-testid="stMainBlockContainer"] hr {
            border-color: #d7e2eb;
            margin: 0.35rem 0;
        }
        @media (max-width: 640px) {
            .stApp .st-key-login-card {
                padding: 0.9rem;
            }
            .login-intro h1 {
                font-size: 1.35rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _, card, _ = st.columns([1, 1.25, 1])
    with card:
        with st.container(border=True, key="login-card"):
            st.markdown(
                """
                <div class="login-intro">
                    <h1>Welcome to Shopwise</h1>
                    <p>Sign in to your shopping assistant.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            notice = st.session_state.pop("auth_notice", None)
            if notice:
                st.success(notice)

            if st.session_state.get("auth_view", "login") == "register":
                st.subheader("Create your account")
                with st.form("registration-form", clear_on_submit=True):
                    full_name = st.text_input("Full name", key="register-name")
                    email = st.text_input("Email", key="register-email")
                    password = st.text_input(
                        "Password (at least 8 characters)",
                        type="password",
                        key="register-password",
                    )
                    confirm_password = st.text_input(
                        "Confirm password",
                        type="password",
                        key="register-confirm-password",
                    )
                    create_account = st.form_submit_button(
                        "Create account",
                        type="primary",
                        width="stretch",
                    )
                if create_account:
                    if password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            register_account(email, password, full_name)
                        except ValueError as error:
                            st.error(str(error))
                        except (OSError, sqlite3.Error):
                            st.error("Account storage is unavailable. Try again.")
                        else:
                            st.session_state.auth_view = "login"
                            st.session_state.auth_notice = (
                                "Account created. Sign in with your new credentials."
                            )
                            st.rerun()
                if st.button("Back to login", width="stretch"):
                    st.session_state.auth_view = "login"
                    st.rerun()
                return

            with st.form("login-form", clear_on_submit=True):
                email = st.text_input("Email", key="login-email")
                password = st.text_input(
                    "Password",
                    type="password",
                    key="login-password",
                )
                login = st.form_submit_button(
                    "Login",
                    type="primary",
                    width="stretch",
                )
            if login:
                try:
                    account = authenticate_account(email, password)
                except (OSError, sqlite3.Error):
                    st.error("Account storage is unavailable. Try again.")
                else:
                    if account is None:
                        st.error("Invalid email or password.")
                    else:
                        st.session_state.access_mode = "authenticated"
                        st.session_state.authenticated_email = account["email"]
                        st.session_state.authenticated_name = account["full_name"]
                        st.session_state.auth_view = "login"
                        st.rerun()

            st.markdown(
                "<p style='text-align:center; margin-top:1rem'>"
                "Don't have an account?</p>",
                unsafe_allow_html=True,
            )
            if st.button("Create an account", width="stretch"):
                st.session_state.auth_view = "register"
                st.rerun()
            st.divider()
            _, guest_button, _ = st.columns([1, 2, 1])
            if guest_button.button(
                "Continue as Guest",
                width="stretch",
                key="continue-as-guest",
            ):
                st.session_state.access_mode = "guest"
                st.rerun()
            st.caption("Browse products without creating an account.")


def _inject_store_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #f4f7f8;
            color: #16313c;
        }
        .stApp [data-testid="stMainBlockContainer"] {
            max-width: 1480px;
            padding-top: 1.1rem;
            padding-bottom: 4rem;
        }
        .stApp [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid #e0e8eb;
        }
        .stApp [data-testid="stWidgetLabel"] p,
        .stApp label,
        .stApp [data-testid="stMarkdownContainer"] p {
            color: #344e59;
        }
        .stApp [data-testid="stTextInput"] input,
        .stApp [data-testid="stNumberInput"] input {
            background: #ffffff;
            color: #16313c;
            border-color: #cbd9de;
        }
        .stApp [data-testid="stTextInput"] input:focus,
        .stApp [data-testid="stNumberInput"] input:focus {
            border-color: #087f78;
            box-shadow: 0 0 0 1px #087f78;
        }
        .stApp [data-testid="stMainBlockContainer"] h1,
        .stApp [data-testid="stMainBlockContainer"] h2,
        .stApp [data-testid="stMainBlockContainer"] h3,
        .stApp [data-testid="stSidebar"] h1,
        .stApp [data-testid="stSidebar"] h2,
        .stApp [data-testid="stSidebar"] h3 {
            color: #16313c;
        }
        .st-key-ai-chat-launcher {
            position: fixed;
            right: 1.25rem;
            bottom: 1rem;
            z-index: 1000;
            width: 6rem;
        }
        .st-key-ai-chat-launcher button {
            width: 6rem;
            min-height: 3.25rem;
            border-radius: 2rem;
            background: #087f78;
            box-shadow: 0 8px 24px rgba(18, 63, 68, 0.22);
        }
        .st-key-ai-chat-launcher button,
        .st-key-ai-chat-launcher button p,
        .st-key-ai-chat-launcher button span {
            color: #ffffff !important;
        }
        div[role="dialog"] {
            width: min(360px, calc(100vw - 2rem)) !important;
            max-width: calc(100vw - 2rem) !important;
            border: 1px solid #dce6e9;
            border-radius: 16px;
            box-shadow: 0 14px 42px rgba(20, 47, 57, 0.18);
        }
        .product-image-placeholder {
            display: grid;
            min-height: 145px;
            place-items: center;
            margin: 0.2rem 0 0.8rem;
            border-radius: 12px;
            background: linear-gradient(145deg, #eef4f5, #e4edef);
            color: #63818a;
            font-size: 0.9rem;
        }
        @media (max-width: 640px) {
            .stApp [data-testid="stMainBlockContainer"] {
                padding: 0.7rem 0.8rem 5rem;
            }
            .product-image-placeholder {
                min-height: 110px;
            }
            .st-key-ai-chat-launcher {
                right: 0.75rem;
                bottom: 0.75rem;
                width: 4.75rem;
            }
            .st-key-ai-chat-launcher button {
                width: 4.75rem;
            }
            div[role="dialog"] {
                width: calc(100vw - 1.5rem) !important;
                max-width: calc(100vw - 1.5rem) !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _clear_shopping_session() -> None:
    for key in (
        "cart",
        "wishlist",
        "chat_messages",
        "agent_history",
        "demo_checkout_complete",
        "store_page",
        "catalog_search_query",
    ):
        st.session_state.pop(key, None)
    st.session_state.pop("access_mode", None)
    st.session_state.pop("authenticated_email", None)
    st.session_state.pop("authenticated_name", None)


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
    ):
        st.session_state.pop(key, None)


def _sync_category_from_nav() -> None:
    st.session_state["category_select"] = st.session_state.get(
        "category_nav", "All Categories"
    )


def _sync_category_from_sidebar() -> None:
    st.session_state["category_nav"] = st.session_state.get(
        "category_select", "All Categories"
    )


def _render_store_header() -> None:
    cart_count = sum(st.session_state.cart.values())
    wishlist_count = len(st.session_state.wishlist)
    header = st.columns([1.3, 4.3, 3.7], vertical_alignment="center")
    with header[0]:
        st.markdown("**Shopwise**")
    with header[1]:
        with st.form("catalog-search-form", border=False):
            search_columns = st.columns([5, 1], vertical_alignment="bottom")
            query = search_columns[0].text_input(
                "Search the catalog",
                placeholder="Search products or brands",
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
            st.session_state.store_page = "shop"
    with header[2]:
        if st.session_state.access_mode == "authenticated":
            st.badge(
                st.session_state.get("authenticated_name", "Shopper"),
                icon=":material/person:",
                color="gray",
            )
            exit_label = "Log out"
            exit_help = "End this account session"
        else:
            st.badge("Guest", icon=":material/person:", color="gray")
            exit_label = "Login"
            exit_help = "Return to the login screen"
        actions = st.columns([1, 1.1, 1], vertical_alignment="center")
        if actions[0].button(
            "Cart",
            key="open-cart",
            help=f"Open cart · {cart_count} items",
            width="stretch",
        ):
            st.session_state.store_page = "cart"
        actions[0].badge(
            str(cart_count),
            icon=":material/shopping_cart:",
            color="primary",
            help=f"{cart_count} units in your cart",
        )
        if actions[1].button(
            "Saved",
            key="open-wishlist",
            help=f"Open wishlist · {wishlist_count} saved products",
            width="stretch",
        ):
            st.session_state.store_page = "wishlist"
        actions[1].badge(
            str(wishlist_count),
            icon=":material/favorite:",
            color="primary",
            help=f"{wishlist_count} products saved",
        )
        if actions[2].button(
            exit_label,
            key="exit-store",
            help=exit_help,
            width="stretch",
        ):
            _clear_shopping_session()
            st.session_state.auth_view = "login"
            st.rerun()
    st.divider()


def _render_product(
    product: dict[str, Any],
    *,
    grid_view: bool,
) -> None:
    product_id = product["id"]
    stock = product["stock"]
    is_saved = product_id in st.session_state.wishlist
    with st.container(border=True, key=f"product-card-{product_id}"):
        st.markdown(
            '<div class="product-image-placeholder" '
            'role="img" aria-label="Product image not available">'
            '<span aria-hidden="true">Image not available</span></div>',
            unsafe_allow_html=True,
        )
        if grid_view:
            st.subheader(product["name"])
            st.markdown(f"### ₹{product['price']:,.2f}")
            st.caption(
                f"{product.get('brand') or '—'} · "
                f"{product.get('category') or '—'}"
            )
        else:
            details, actions = st.columns([3, 1], vertical_alignment="center")
            with details:
                st.subheader(product["name"])
                st.markdown(f"### ₹{product['price']:,.2f}")
                st.caption(
                    f"{product.get('brand') or '—'} · "
                    f"{product.get('category') or '—'}"
                )

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
            action_columns = st.columns([1.3, 1], vertical_alignment="center")
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
                width="stretch",
            )
        else:
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
                st.toast("Removed from your session wishlist.")
            else:
                st.session_state.wishlist.add(product_id)
                st.toast("Added to your session wishlist.")
            st.rerun()


def _render_shop(facets: dict[str, list[str]]) -> None:
    st.header("Shop the catalog")
    if st.session_state.access_mode == "authenticated":
        st.subheader(
            f"Welcome, {st.session_state.get('authenticated_name', 'Shopper')}"
        )
    else:
        st.caption("Browsing as a guest · cart and wishlist are temporary to this session")

    category_options = ["All Categories", *facets["categories"]]
    st.pills(
        "Browse categories",
        category_options,
        key="category_nav",
        default="All Categories",
        on_change=_sync_category_from_nav,
        width="stretch",
        help="Select a category to filter the live product catalog.",
    )

    try:
        catalog = load_catalog()
    except (OSError, sqlite3.Error, ValueError):
        st.error("The product catalog could not be loaded. Please try again.")
        return
    if not catalog:
        st.info("The catalog is empty.")
        return

    largest_price = max(float(product["price"]) for product in catalog)
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
        )
        st.number_input(
            "Minimum price (₹)",
            min_value=0.0,
            max_value=largest_price,
            value=0.0,
            step=100.0,
            key="min_price_filter",
        )
        st.number_input(
            "Maximum price (₹)",
            min_value=0.0,
            max_value=largest_price,
            value=largest_price,
            step=100.0,
            key="max_price_filter",
        )
        st.slider(
            "Minimum customer rating",
            min_value=0.0,
            max_value=5.0,
            value=0.0,
            step=0.5,
            key="rating_filter",
        )
        st.checkbox("In stock only", key="stock_filter")
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
            default="Grid",
            key="product_view",
            label_visibility="collapsed",
        )
    with result_column:
        st.caption(f"{len(catalog)} products in the Shopwise catalog")

    min_price = st.session_state.get("min_price_filter", 0.0)
    max_price = st.session_state.get("max_price_filter", largest_price)
    if min_price > max_price:
        st.error("Minimum price cannot be greater than maximum price.")
        return

    selected_category = st.session_state.get(
        "category_select", "All Categories"
    )
    selected_brand = st.session_state.get("brand_select", "All Brands")
    sort_options = {
        "Relevance": "relevance",
        "Price: low to high": "price_low_to_high",
        "Price: high to low": "price_high_to_low",
        "Highest rated": "highest_rated",
        "Product name: A–Z": "name_ascending",
    }
    try:
        products = browse_catalog(
            search_term=st.session_state.get("catalog_search_query", ""),
            min_price=min_price,
            max_price=max_price,
            min_rating=st.session_state.get("rating_filter", 0.0),
            in_stock=st.session_state.get("stock_filter", False),
            category=(
                selected_category
                if selected_category != "All Categories"
                else None
            ),
            brand=selected_brand if selected_brand != "All Brands" else None,
            sort_by=sort_options.get(
                st.session_state.get("sort_filter", "Relevance"),
                "relevance",
            ),
        )
    except (OSError, sqlite3.Error, ValueError):
        st.error("Those search filters could not be applied. Check the price range.")
        return

    active_search = st.session_state.get("catalog_search_query", "")
    if active_search:
        st.caption(f'Search results for “{active_search}”')
    st.write(f"**{len(products)} matching products**")
    if not products:
        st.info("No products match those filters. Try widening your search.")
        return

    grid_view = st.session_state.get("product_view", "Grid") == "Grid"
    if grid_view:
        product_columns = st.columns(3, gap="medium")
        for index, product in enumerate(products):
            with product_columns[index % len(product_columns)]:
                _render_product(product, grid_view=True)
    else:
        for product in products:
            _render_product(product, grid_view=False)

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


def _load_cart_products() -> dict[int, dict[str, Any]] | None:
    try:
        rows = get_products_by_ids(list(st.session_state.cart))
    except (OSError, sqlite3.Error, ValueError):
        st.error("The current catalog could not be checked. Please retry.")
        return None
    return {product["id"]: product for product in rows}


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
                st.caption(
                    f"Line total: ₹{line_total:,.2f}"
                )
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


def _render_demo_checkout() -> None:
    st.header("Demo checkout")
    st.warning(
        "This is a demonstration only. No payment is taken and no order is saved."
    )
    if not st.session_state.cart:
        st.info("Your cart is empty. Add products before reviewing checkout.")
        return

    products_by_id = _load_cart_products()
    if products_by_id is None:
        return
    for product_id in st.session_state.cart:
        if product_id not in products_by_id:
            st.error("A cart item is no longer available. Remove it before checkout.")
            return
    try:
        total = validate_checkout(st.session_state.cart, products_by_id)
    except (KeyError, ValueError) as error:
        st.error(f"Your cart needs attention before checkout: {error}")
        return

    st.subheader("Order summary")
    for product_id, quantity in st.session_state.cart.items():
        product = products_by_id[product_id]
        line_total = Decimal(str(product["price"])) * quantity
        st.write(
            f"{product['name']} · {quantity} × "
            f"₹{product['price']:,.2f} = ₹{line_total:,.2f}"
        )
    st.markdown(f"### Total: ₹{total:,.2f}")
    if st.session_state.demo_checkout_complete:
        st.success("Demo checkout complete. No order was placed or stored.")
    elif st.button(
        "Complete demo checkout",
        type="primary",
        icon=":material/check_circle:",
    ):
        st.session_state.demo_checkout_complete = True
        st.rerun()
    if st.button("Return to cart", icon=":material/arrow_back:"):
        st.session_state.store_page = "cart"
        st.rerun()


def _render_wishlist() -> None:
    st.header("Your wishlist")
    st.info(
        "This wishlist is temporary and stored only in this browser session."
    )
    if not st.session_state.wishlist:
        st.write("No saved products yet.")
        return
    try:
        rows = get_products_by_ids(list(st.session_state.wishlist))
    except (OSError, sqlite3.Error, ValueError):
        st.error("The wishlist could not be loaded from the catalog.")
        return
    products_by_id = {product["id"]: product for product in rows}
    missing = st.session_state.wishlist - products_by_id.keys()
    if missing:
        st.warning("One or more saved products are no longer available.")
    columns = st.columns(3, gap="medium")
    for index, product in enumerate(rows):
        with columns[index % len(columns)]:
            _render_product(product, grid_view=True)


def _chat_error_message(error: Exception) -> str:
    load_dotenv(PROJECT_ROOT / ".env")
    if not os.getenv("GEMINI_API_KEY"):
        return (
            "The AI assistant is not configured yet. Add GEMINI_API_KEY to "
            "the project-root .env file, then restart Shopwise."
        )
    if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        return "The AI request timed out. Please try again."
    return (
        "The AI assistant could not complete this request. "
        "Check Gemini connectivity and try again."
    )


def _render_chat_launcher() -> None:
    with st.popover(
        "Chat",
        icon=":material/chat:",
        key="ai-chat-launcher",
        width=360,
        on_change="rerun",
    ):
        st.markdown("**Shopwise AI Assistant**")
        with st.container(height=110, border=True):
            if not st.session_state.chat_messages:
                st.caption(
                    "Catalog-backed help with products, budgets, and availability."
                )
            for message in st.session_state.chat_messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
        with st.form("shopwise-chat-form", clear_on_submit=True):
            input_column, send_column = st.columns(
                [4, 1],
                vertical_alignment="bottom",
            )
            prompt = input_column.text_input(
                "Message the shopping assistant",
                placeholder="Ask about products",
                label_visibility="collapsed",
            )
            send = send_column.form_submit_button(
                "Send",
                icon=":material/send:",
                type="primary",
                width="stretch",
            )
        if send and prompt.strip():
            st.session_state.chat_messages.append(
                {"role": "user", "content": prompt.strip()}
            )
            try:
                with st.spinner("Checking the catalog with Gemini…"):
                    answer = asyncio.run(
                        _respond_with_agent(
                            prompt.strip(),
                            st.session_state.agent_history,
                        )
                    )
                answer = _ground_chat_answer(answer)
            except Exception as error:
                answer = _chat_error_message(error)
                st.session_state.chat_messages.append(
                    {"role": "assistant", "content": answer}
                )
                st.error(answer)
            else:
                st.session_state.chat_messages.append(
                    {"role": "assistant", "content": answer}
                )
                with st.chat_message("assistant"):
                    st.markdown(answer)


def main() -> None:
    st.set_page_config(page_title="Shopwise", page_icon="🛍️", layout="wide")
    if st.session_state.get("access_mode") not in {"guest", "authenticated"}:
        _render_login_screen()
        return

    _inject_store_styles()
    for key, initial_value in (
        ("cart", {}),
        ("wishlist", set()),
        ("chat_messages", []),
        ("agent_history", []),
        ("store_page", "shop"),
        ("demo_checkout_complete", False),
        ("catalog_search_query", ""),
    ):
        if key not in st.session_state:
            st.session_state[key] = initial_value

    _render_store_header()
    try:
        facets = load_catalog_facets()
    except (OSError, sqlite3.Error):
        st.error("Shopwise could not load product categories. Please try again.")
        return

    page = st.session_state.store_page
    if page == "cart":
        _render_cart()
    elif page == "checkout":
        _render_demo_checkout()
    elif page == "wishlist":
        _render_wishlist()
    else:
        st.session_state.store_page = "shop"
        _render_shop(facets)

    _render_chat_launcher()


if __name__ == "__main__":
    main()
