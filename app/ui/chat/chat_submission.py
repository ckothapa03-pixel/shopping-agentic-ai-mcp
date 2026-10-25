import asyncio
import time
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from app.agent.agent import gemini_timeout_seconds
from app.agent.chat_runtime import _record_chat_stage, _respond_with_agent
from app.ui.chat.chat_errors import _chat_error_message, _classify_chat_error, _log_chat_exception
from app.ui.chat.chat_grounding import ground_chat_answer as _ground_chat_answer
from app.ui.chat.chat_product import _render_chat_product

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CHAT_TIMEOUT_PADDING_SECONDS = 30

__all__ = [
    "_begin_chat_submission",
    "_clear_chat_prompt",
    "_process_chat_submission",
    "_recover_interrupted_chat_reply",
]

def _recover_interrupted_chat_reply() -> None:
    pending = st.session_state.get("chat_pending_reply")

    if not isinstance(pending, dict):
        st.session_state.chat_processing = False
        return

    index = pending.get("assistant_index")
    messages = st.session_state.chat_messages

    if (
        isinstance(index, int)
        and 0 <= index < len(messages)
        and messages[index].get("role") == "assistant"
        and messages[index].get("pending")
    ):
        messages[index]["content"] = (
            "I couldn't complete that reply. Please send your message again."
        )
        messages[index].pop("pending", None)

    st.session_state.chat_pending_reply = None
    st.session_state.chat_processing = False

def _clear_chat_prompt() -> None:
    """Clear the shared form input for both Enter and button submissions."""
    prompt = st.session_state.get("chat-prompt", "")

    if prompt.strip():
        st.session_state["chat-submitted-prompt"] = prompt
    else:
        st.session_state.pop("chat-submitted-prompt", None)

    st.session_state["chat-prompt"] = ""

def _begin_chat_submission(submitted_message: str) -> dict[str, Any]:
    """Persist the prompt and a pending assistant turn before slow work starts."""
    st.session_state.chat_messages.append(
        {"role": "user", "content": submitted_message}
    )

    assistant_index = len(st.session_state.chat_messages)
    assistant_entry = {
        "role": "assistant",
        "content": "I'm preparing a reply…",
        "pending": True,
    }

    st.session_state.chat_messages.append(assistant_entry)
    st.session_state.chat_pending_reply = {
        "assistant_index": assistant_index,
        "user_message": submitted_message,
    }
    st.session_state.chat_processing = True

    return assistant_entry

def _process_chat_submission(
    submitted_message: str,
    assistant_entry: dict[str, Any],
    response_slot: Any,
) -> None:
    """Run the agent after the pending turn has already been rendered."""
    product_results: list[dict[str, Any]] = []
    product_search_performed: list[bool] = []

    submission_completed = False
    timing_started_at = time.perf_counter()
    _record_chat_stage(timing_started_at, "submission_received")

    def record_stage(stage: str) -> None:
        _record_chat_stage(timing_started_at, stage)

    try:
        # The configured SDK timeout governs the Gemini request. Leave a
        # bounded cushion for client setup/teardown and the MCP product flow.
        load_dotenv(PROJECT_ROOT / ".env")

        answer = asyncio.run(
            asyncio.wait_for(
                _respond_with_agent(
                    submitted_message,
                    st.session_state.agent_history,
                    product_results,
                    product_search_performed,
                    product_search_loader=lambda: st.spinner(
                        "Searching the catalog…"
                    ),
                    on_text_delta=None,
                    on_stage=record_stage,
                ),
                timeout=gemini_timeout_seconds() + CHAT_TIMEOUT_PADDING_SECONDS,
            )
        )

        answer = _ground_chat_answer(answer, submitted_message)
        record_stage("response_completed")

        if product_search_performed:
            marker = "Catalog results from shopping.db:"
            answer = answer.split(marker, 1)[0].strip()

            if not product_results:
                answer = (
                    "I couldn't find matching products in the catalog. "
                    "Try a different search or broaden your filters."
                )
            elif not answer:
                answer = "Here are matching options from the Shopwise catalog."

        assistant_entry["content"] = answer or (
            "I couldn't prepare a reply. Please try again."
        )
        assistant_entry["products"] = product_results
        submission_completed = True

    except Exception as error:
        category, _ = _classify_chat_error(error)
        record_stage("timeout_raised" if category == "timeout" else "exception_raised")
        _log_chat_exception(error)
        assistant_entry["content"] = _chat_error_message(error)
        submission_completed = True

    finally:
        if submission_completed:
            assistant_entry.pop("pending", None)
            st.session_state.chat_pending_reply = None
            st.session_state.chat_processing = False

            with response_slot.container():
                st.markdown(assistant_entry["content"])

                for product in assistant_entry.get("products", []):
                    _render_chat_product(product)

            # The final answer is already written into its visible slot above.
            # Rerun once to re-enable the composer and render the settled state.
            st.rerun()
