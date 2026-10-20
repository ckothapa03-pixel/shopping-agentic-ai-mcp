import asyncio
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from google import genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.agent import respond
from app.authentication import authenticate_account, register_account
from app.cart import add_to_cart, cart_total, remove_from_cart, update_cart_quantity
from app.tools.products_tool import search_products

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@st.cache_data(ttl=60)
def load_catalog() -> list[dict[str, Any]]:
    return search_products(limit=1000)


@st.cache_data(ttl=15)
def find_catalog_products(search_term: str, max_price: float) -> list[dict[str, Any]]:
    return search_products(
        search_term=search_term,
        max_price=max_price,
        limit=1000,
    )


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


def _safe_error_detail(error: Exception) -> str:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY")
    detail = str(error)
    if api_key:
        detail = detail.replace(api_key, "[REDACTED]")
    return re.sub(
        r"(?i)(?:AIza[0-9A-Za-z_-]{20,}|Bearer\s+\S+)",
        "[REDACTED]",
        detail,
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


def _clear_shopping_session() -> None:
    for key in ("cart", "chat_messages", "agent_history"):
        st.session_state.pop(key, None)
    st.session_state.pop("access_mode", None)
    st.session_state.pop("authenticated_email", None)
    st.session_state.pop("authenticated_name", None)


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
                        use_container_width=True,
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
                if st.button("Back to login", use_container_width=True):
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
                    use_container_width=True,
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
            if st.button("Create an account", use_container_width=True):
                st.session_state.auth_view = "register"
                st.rerun()
            st.divider()
            _, guest_button, _ = st.columns([1, 2, 1])
            if guest_button.button(
                "Continue as Guest",
                use_container_width=True,
                key="continue-as-guest",
            ):
                st.session_state.access_mode = "guest"
                st.rerun()
            st.caption("Browse products without creating an account.")


def _render_product(product: dict[str, Any]) -> None:
    product_id = product["id"]
    stock = product["stock"]
    with st.container(border=True):
        st.subheader(product["name"])
        st.write(f"**₹{product['price']:,.2f}**")
        st.write(
            f"Rating: {product['rating_avg']}/5 "
            f"({product['rating_count']} reviews)"
        )
        availability = f"In stock: {stock}" if stock > 0 else "Out of stock"
        st.write(f"{availability} · {product['brand']} · {product['category']}")
        with st.expander("Product details"):
            st.write(product["description"] or "No description available.")
            st.caption(f"SKU: {product['sku']} · MRP: ₹{product['mrp']:,.2f}")
        if st.button(
            "Add to cart",
            key=f"add-product-{product_id}",
            disabled=stock < 1,
            use_container_width=True,
        ):
            try:
                st.session_state.cart = add_to_cart(
                    st.session_state.cart,
                    product,
                )
                st.toast(f"Added {product['name']} to your cart.")
            except ValueError as error:
                st.error(str(error))


def _render_shop() -> None:
    st.header("Shop the catalog")
    try:
        catalog = load_catalog()
    except Exception as error:
        st.error(f"Could not load products from shopping.db: {error}")
        return

    if not catalog:
        st.info("The catalog is empty.")
        return

    largest_price = max(float(product["price"]) for product in catalog)
    filters = st.columns([2, 1])
    search_term = filters[0].text_input(
        "Search products",
        placeholder="Try mouse, headphones, or a brand",
    )
    max_price = filters[1].number_input(
        "Maximum price (₹)",
        min_value=0.0,
        max_value=largest_price,
        value=largest_price,
        step=100.0,
    )

    try:
        products = find_catalog_products(search_term, max_price)
    except Exception as error:
        st.error(f"Product search failed: {error}")
        return

    if not products:
        st.info("No products match those filters.")
    else:
        product_columns = st.columns(3)
        for index, product in enumerate(products):
            with product_columns[index % len(product_columns)]:
                _render_product(product)

    st.divider()
    st.subheader("Your cart")
    if not st.session_state.cart:
        st.info("Your cart is empty. Add a product to get started.")
        return

    products_by_id = {product["id"]: product for product in catalog}
    for product_id, quantity in list(st.session_state.cart.items()):
        product = products_by_id.get(product_id)
        if product is None:
            st.error(f"Cart product {product_id} is no longer in the catalog.")
            continue
        cart_columns = st.columns([3, 1, 1, 1])
        cart_columns[0].write(
            f"**{product['name']}**  \n₹{product['price']:,.2f} each"
        )
        if product["stock"] > 0:
            quantity_key = f"cart-quantity-{product_id}"
            selected_quantity = cart_columns[1].number_input(
                "Quantity",
                min_value=1,
                max_value=product["stock"],
                value=quantity,
                key=quantity_key,
                label_visibility="collapsed",
            )
            if cart_columns[2].button("Update", key=f"update-cart-{product_id}"):
                try:
                    st.session_state.cart = update_cart_quantity(
                        st.session_state.cart,
                        product,
                        selected_quantity,
                    )
                except ValueError as error:
                    st.error(str(error))
        else:
            cart_columns[1].warning("Out of stock")
        if cart_columns[3].button("Remove", key=f"remove-cart-{product_id}"):
            st.session_state.cart = remove_from_cart(
                st.session_state.cart,
                product_id,
            )
            st.rerun()
        current_quantity = st.session_state.cart.get(product_id, quantity)
        st.caption(
            f"Line total: ₹{product['price'] * current_quantity:,.2f}"
        )

    try:
        total = cart_total(st.session_state.cart, products_by_id)
    except ValueError as error:
        st.error(f"Could not calculate your cart total: {error}")
    else:
        st.markdown(f"### Cart total: ₹{total:,.2f}")


def _render_chatbot() -> None:
    st.header("AI shopping assistant")
    st.caption(
        "Ask about products, ratings, availability, or your budget. "
        "Recommendations are grounded in the local catalog."
    )

    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("What are you looking for?")
    if not prompt:
        return

    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Searching the catalog with Gemini..."):
            try:
                answer = asyncio.run(
                    _respond_with_agent(
                        prompt,
                        st.session_state.agent_history,
                    )
                )
                answer = _ground_chat_answer(answer)
            except Exception as error:
                detail = _safe_error_detail(error)
                answer = (
                    "Sorry, I couldn't complete that search. Check that Gemini "
                    "is configured and the local MCP catalog server is available."
                )
                if detail:
                    answer += f"\n\nDetails: `{type(error).__name__}: {detail}`"
                st.session_state.chat_messages.append(
                    {"role": "assistant", "content": answer}
                )
                st.error(answer)
            else:
                st.session_state.chat_messages.append(
                    {"role": "assistant", "content": answer}
                )
                st.markdown(answer)


def main() -> None:
    st.set_page_config(page_title="Agentic AI Shopping", page_icon="🛍️", layout="wide")
    if st.session_state.get("access_mode") not in {"guest", "authenticated"}:
        _render_login_screen()
        return

    for key, initial_value in (
        ("cart", {}),
        ("chat_messages", []),
        ("agent_history", []),
    ):
        if key not in st.session_state:
            st.session_state[key] = initial_value

    toolbar = st.columns([5, 1])
    if st.session_state.access_mode == "authenticated":
        toolbar[0].subheader(
            f"Welcome, {st.session_state.get('authenticated_name', 'Shopper')}"
        )
        exit_label = "Log out"
    else:
        toolbar[0].subheader("Browsing as guest")
        exit_label = "Return to login"
    if toolbar[1].button(exit_label, use_container_width=True):
        _clear_shopping_session()
        st.session_state.auth_view = "login"
        st.rerun()

    shop_tab, chatbot_tab = st.tabs(["Shop", "AI Chatbot"])
    with shop_tab:
        _render_shop()
    with chatbot_tab:
        _render_chatbot()


if __name__ == "__main__":
    main()
