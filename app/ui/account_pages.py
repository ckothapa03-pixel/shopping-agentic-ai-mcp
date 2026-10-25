import streamlit as st

def _render_profile() -> None:
    st.header("Your profile")

    with st.container(border=True):
        st.write(f"**Name:** {st.session_state.get('authenticated_name', 'Shopper')}")
        st.write(f"**Email:** {st.session_state.get('authenticated_email', '')}")
        st.caption("Your Shopwise demo account details.")

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
