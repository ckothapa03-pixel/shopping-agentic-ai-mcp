import sqlite3

import streamlit as st

from app.shopping.authentication import authenticate_account, register_account
from app.shopping.identity import clear_chat_session, enter_guest_session
from app.ui.styles import render_login_styles
from app.ui.error_messages import safe_error_message


def render_login_screen() -> None:
    render_login_styles()
    with st.container(border=True, key="login-card"):
        st.markdown(
            """
            <div class="login-brand" aria-label="Shopwise, Your AI Shopping Assistant">
                <div class="login-wordmark">
                    <svg viewBox="0 0 48 48" aria-hidden="true">
                        <path d="M5 8h5l4.2 21.1a4 4 0 0 0 3.9 3.2h19.2a4 4 0 0 0 3.8-2.8L45 15H15.2l-.8-4H5z"/>
                        <circle cx="20" cy="39" r="3.5"/>
                        <circle cx="36" cy="39" r="3.5"/>
                    </svg>
                    <span class="brand-shop">Shop</span><span class="brand-wise">wise</span>
                </div>
                <p>Your AI Shopping Assistant</p>
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
                    "Password (at least 12 characters)",
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
                    except (OSError, sqlite3.Error) as error:
                        st.error(safe_error_message(error, "Account storage is unavailable. Try again.", event="account_registration_failed"))
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

        st.markdown(
            """
            <div class="login-intro">
                <h1>Welcome Back</h1>
                <p>Sign in to your account</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("login-form", clear_on_submit=True):
            email = st.text_input(
                "Email",
                placeholder="Enter your email address",
                key="login-email",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="login-password",
            )
            login = st.form_submit_button(
                "Sign In",
                type="primary",
                width="stretch",
                key="login-submit",
            )
            with st.container(
                horizontal=True,
                key="login-actions",
                vertical_alignment="center",
            ):
                st.checkbox(
                    "Remember me",
                    disabled=True,
                    help="Persistent sign-in is not implemented. Sessions use the current browser session only.",
                    key="remember-me",
                )
                forgot_password = st.form_submit_button(
                    "Forgot Password?",
                    type="tertiary",
                    key="forgot-password",
                )
        if forgot_password:
            st.info(
                "Secure password recovery is not configured. This app has no "
                "verified identity-recovery method, so your password cannot "
                "be reset here."
            )
        if login:
            try:
                account = authenticate_account(email, password)
            except (OSError, sqlite3.Error) as error:
                st.error(safe_error_message(error, "Account storage is unavailable. Try again.", event="login_storage_failed"))
            else:
                if account is None:
                    st.error("Invalid email or password.")
                else:
                    clear_chat_session(st.session_state)
                    st.session_state.access_mode = "authenticated"
                    st.session_state.authenticated_email = account["email"]
                    st.session_state.authenticated_name = account["full_name"]
                    st.session_state.authenticated_user_id = account["user_id"]
                    st.session_state.auth_view = "login"
                    st.rerun()

        st.markdown(
            '<div class="login-divider"><span>or</span></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "Continue as Guest",
            width="stretch",
            key="continue-as-guest",
        ):
            enter_guest_session(st.session_state)
            st.rerun()
        st.markdown(
            '<p class="login-create-prompt">Don\'t have an account?</p>',
            unsafe_allow_html=True,
        )
        if st.button(
            "Create an Account",
            width="stretch",
            key="create-account",
        ):
            st.session_state.auth_view = "register"
            st.rerun()
