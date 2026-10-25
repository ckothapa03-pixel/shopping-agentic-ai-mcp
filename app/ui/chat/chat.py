import streamlit as st

from app.ui.chat.chat_product import _render_chat_product
from app.ui.chat.chat_submission import _begin_chat_submission, _clear_chat_prompt, _process_chat_submission, _recover_interrupted_chat_reply

__all__ = ["_render_chat_launcher"]

def _render_chat_launcher() -> None:
    _recover_interrupted_chat_reply()

    if not st.session_state.chat_open:
        with st.container(key="chat-launcher"):
            if st.button(
                "Chat",
                key="open-chat",
                icon=":material/chat:",
                help="Open the Shopwise Assistant",
                type="primary",
            ):
                st.session_state.chat_open = True
                st.rerun()
        return

    # Form callbacks run before Streamlit executes the page from top to
    # bottom. Consume the captured value here, before rendering the popup,
    # so the ordinary render pass includes the completed exchange. Do not
    # gate processing on the submit button's return value: its value can be
    # false after the callback has already cleared the form widget.
    submitted_message = st.session_state.pop("chat-submitted-prompt", "").strip()

    assistant_entry = (
        _begin_chat_submission(submitted_message) if submitted_message else None
    )
    response_slot = None

    with st.container(key="chat-popup", border=True):
        with st.container(key="chat-popup-header"):
            title, close_column = st.columns(
                [4.4, 1.8],
                vertical_alignment="center",
            )
            title.markdown("#### :material/smart_toy: Shopwise Assistant")

            if close_column.button(
                "Close",
                key="close-chat",
                icon=":material/close:",
                help="Close the assistant",
                width="stretch",
            ):
                st.session_state.chat_open = False
                st.rerun()

        chat_height = min(
            390,
            max(160, 72 * (len(st.session_state.chat_messages) + 1)),
        )

        with st.container(
            height=chat_height,
            border=False,
            key="chat-message-list",
            autoscroll=True,
        ):
            if not st.session_state.chat_messages:
                with st.chat_message("assistant", avatar=":material/smart_toy:"):
                    st.markdown(
                        "Hello! I can help you find products, compare catalog "
                        "details, or answer questions about Shopwise."
                    )

            for message in st.session_state.chat_messages:
                avatar = (
                    ":material/person:"
                    if message["role"] == "user"
                    else ":material/smart_toy:"
                )

                with st.chat_message(message["role"], avatar=avatar):
                    if message.get("pending") and message is assistant_entry:
                        response_slot = st.empty()
                        response_slot.markdown("**Shopwise is thinking…**")
                    else:
                        st.markdown(message["content"])

                        for product in message.get("products", []):
                            _render_chat_product(product)

        with st.form(
            "shopwise-chat-form",
            clear_on_submit=True,
            enter_to_submit=True,
        ):
            input_column, send_column = st.columns(
                [3.6, 1.4],
                vertical_alignment="center",
            )

            input_column.text_input(
                "Message the shopping assistant",
                placeholder="Ask about products...",
                label_visibility="collapsed",
                key="chat-prompt",
                disabled=bool(assistant_entry),
            )

            send_column.form_submit_button(
                "Send",
                icon=":material/send:",
                type="primary",
                width="stretch",
                disabled=bool(assistant_entry),
                on_click=_clear_chat_prompt,
            )

    if (
        submitted_message
        and assistant_entry is not None
        and response_slot is not None
    ):
        _process_chat_submission(
            submitted_message,
            assistant_entry,
            response_slot,
        )
