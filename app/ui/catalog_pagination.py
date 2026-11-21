import streamlit as st


def render_page_controls(
    current_page: int,
    total_pages: int,
    *,
    key_prefix: str,
) -> None:
    if total_pages <= 1:
        return
    first_page = max(1, min(current_page - 2, total_pages - 4))
    page_numbers = range(first_page, min(total_pages, first_page + 4) + 1)
    controls = st.columns(len(page_numbers) + 2, vertical_alignment="center")
    if controls[0].button(
        "Previous",
        key=f"{key_prefix}-previous",
        disabled=current_page == 1,
        width="stretch",
    ):
        st.session_state.catalog_page = current_page - 1
        st.rerun()
    for column, page_number in zip(controls[1:-1], page_numbers):
        if column.button(
            str(page_number),
            key=f"{key_prefix}-page-{page_number}",
            type="primary" if page_number == current_page else "secondary",
            width="stretch",
        ):
            st.session_state.catalog_page = page_number
            st.rerun()
    if controls[-1].button(
        "Next",
        key=f"{key_prefix}-next",
        disabled=current_page == total_pages,
        width="stretch",
    ):
        st.session_state.catalog_page = current_page + 1
        st.rerun()
    st.caption(f"Page {current_page} of {total_pages}")
