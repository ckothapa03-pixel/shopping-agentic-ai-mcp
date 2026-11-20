import sqlite3
import streamlit as st

from app.db.address_repository import (
    create_address,
    delete_address,
    list_addresses,
)
from app.shopping.identity import require_authenticated_user


def _render_addresses() -> None:
    st.header("Delivery addresses")
    try:
        user_id = require_authenticated_user(st.session_state)
        addresses = list_addresses(user_id)
    except (PermissionError, OSError, sqlite3.Error) as error:
        st.error(str(error))
        return

    for address in addresses:
        with st.container(border=True):
            st.write(f"**{address['label']}** {'(Default)' if address['is_default'] else ''}")
            st.write(address["line1"])
            st.caption(f"{address['city']}, {address['state']} - {address['pincode']}")
            if st.button("Delete", key=f"delete-address-{address['id']}"):
                try:
                    delete_address(user_id, address["id"])
                    st.rerun()
                except (PermissionError, sqlite3.Error, OSError) as error:
                    st.error(str(error))

    with st.expander("Add address"):
        with st.form("add-address-form"):
            label = st.text_input("Label")
            line1 = st.text_input("Address")
            city = st.text_input("City")
            state = st.text_input("State")
            pincode = st.text_input("Pincode")
            is_default = st.checkbox("Set as default")
            submitted = st.form_submit_button("Save address", type="primary")
        if submitted:
            try:
                create_address(user_id, label, line1, city, state, pincode, is_default)
                st.success("Address saved.")
                st.rerun()
            except (ValueError, PermissionError, sqlite3.Error, OSError) as error:
                st.error(str(error))
