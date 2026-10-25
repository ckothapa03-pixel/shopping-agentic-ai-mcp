import sqlite3

import streamlit as st

from app.shopping.authentication import authenticate_account, register_account
from app.ui.styles import render_login_styles


def render_login_screen() -> None:
    render_login_styles()
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
