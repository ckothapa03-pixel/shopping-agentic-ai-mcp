import sqlite3

import streamlit as st

from app.shopping.authentication import (
    change_account_password,
    get_account_profile,
    update_account_profile,
)
from app.shopping.identity import prepare_login_session
from app.ui.error_messages import safe_error_message

def _render_profile() -> None:
    st.header("Your profile")

    email = st.session_state.get("authenticated_email", "")
    profile = None
    try:
        profile = get_account_profile(email)
    except (OSError, sqlite3.Error, ValueError):
        st.error("Your profile could not be loaded.")

    with st.container(border=True):
        st.write(f"**Name:** {st.session_state.get('authenticated_name', 'Shopper')}")
        st.write(f"**Email:** {email}")
        if profile is not None:
            st.caption("Linked to an active Shopwise shopping profile.")
        else:
            st.warning("This account is not currently linked to a shopping profile.")

    with st.expander("Edit profile"):
        with st.form("account-profile-form"):
            full_name = st.text_input(
                "Full name",
                value=st.session_state.get("authenticated_name", ""),
            )
            submitted = st.form_submit_button(
                "Save profile",
                type="primary",
            )
        if submitted:
            try:
                updated = update_account_profile(email, full_name)
            except (OSError, sqlite3.Error, ValueError) as error:
                st.error(safe_error_message(error, "Your profile could not be updated.", event="profile_update_failed", allow_value_error=True))
            else:
                st.session_state.authenticated_name = updated["full_name"]
                st.success("Profile updated.")
                st.rerun()

    with st.expander("Change password"):
        with st.form("account-password-form"):
            current_password = st.text_input(
                "Current password",
                type="password",
            )
            new_password = st.text_input(
                "New password",
                type="password",
            )
            confirm_password = st.text_input(
                "Confirm new password",
                type="password",
            )
            submitted = st.form_submit_button(
                "Change password",
                type="primary",
            )
        if submitted:
            if new_password != confirm_password:
                st.error("New passwords do not match.")
            else:
                try:
                    change_account_password(
                        email,
                        current_password,
                        new_password,
                    )
                except (OSError, sqlite3.Error, ValueError) as error:
                    st.error(safe_error_message(error, "Your password could not be changed.", event="password_change_failed", allow_value_error=True))
                else:
                    prepare_login_session(st.session_state)
                    st.session_state.auth_notice = (
                        "Password changed. Sign in again with your new password."
                    )
                    st.rerun()

    if st.button("Back to shopping", icon=":material/storefront:"):
        st.session_state.store_page = "shop"
        st.rerun()

def _render_settings() -> None:
    st.header("Settings")

    layout = st.radio(
        "Default catalog layout",
        options=["Grid", "List"],
        key="settings_catalog_layout",
        index=(
            0
            if st.session_state.get("catalog_layout_preference", "Grid") == "Grid"
            else 1
        ),
        horizontal=True,
    )

    if st.button("Save settings", type="primary"):
        st.session_state.catalog_layout_preference = layout
        st.session_state.store_page = "shop"
        st.toast(f"Catalog layout set to {layout.lower()} view.")
        st.rerun()

    if st.button("Back to shopping"):
        st.session_state.store_page = "shop"
        st.rerun()
