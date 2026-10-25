from pathlib import Path

import streamlit as st

CSS_DIRECTORY = Path(__file__).resolve().parents[2] / "assets" / "css"


def _render_stylesheet(filename: str) -> None:
    stylesheet = CSS_DIRECTORY / filename
    st.markdown(stylesheet.read_text(encoding="utf-8"), unsafe_allow_html=True)


def render_login_styles() -> None:
    _render_stylesheet("login.css")


def render_store_styles() -> None:
    _render_stylesheet("store.css")
