import os
import sys
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, ContextManager

from dotenv import load_dotenv
from google import genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.agent.agent import respond

PROJECT_ROOT = Path(__file__).resolve().parents[2]

__all__ = ["_record_chat_stage", "_respond_with_agent"]

def _record_chat_stage(
    started_at: float,
    stage: str,
    stage_elapsed_seconds: float | None = None,
) -> None:
    """Log timing-only diagnostics when explicitly enabled for debugging."""
    if os.getenv("SHOPWISE_CHAT_TIMING", "").strip().casefold() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return
    elapsed = time.perf_counter() - started_at
    details = f"stage={stage} elapsed_seconds={elapsed:.3f}"
    if stage_elapsed_seconds is not None:
        details += f" stage_elapsed_seconds={stage_elapsed_seconds:.3f}"
    logging.getLogger("app.agent").debug("Shopwise chat timing %s", details)


async def _respond_with_agent(
    user_message: str,
    conversation_history: list[dict[str, Any]],
    product_results: list[dict[str, Any]] | None = None,
    product_search_performed: list[bool] | None = None,
    product_search_loader: Callable[[], ContextManager[Any]] | None = None,
    on_text_delta: Callable[[str], None] | None = None,
    on_stage: Callable[[str], None] | None = None,
    user_id: str | None = None,
) -> str:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Gemini is not configured. Set GEMINI_API_KEY in the project-root "
            ".env file or in your environment, then restart the app."
        )

    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    if on_stage is not None:
        on_stage("gemini_client_initializing")

    async with genai.Client(api_key=api_key).aio as client:
        return await _respond_with_client(
            client=client,
            user_message=user_message,
            model=model,
            conversation_history=conversation_history,
            product_results=product_results,
            product_search_performed=product_search_performed,
            product_search_loader=product_search_loader,
            on_text_delta=on_text_delta,
            on_stage=on_stage,
            user_id=user_id,
        )


async def _respond_with_client(
    client: Any,
    user_message: str,
    model: str,
    conversation_history: list[dict[str, Any]],
    product_results: list[dict[str, Any]] | None,
    product_search_performed: list[bool] | None,
    product_search_loader: Callable[[], ContextManager[Any]] | None,
    on_text_delta: Callable[[str], None] | None,
    on_stage: Callable[[str], None] | None,
    user_id: str | None = None,
) -> str:
    if on_stage is not None:
        on_stage("gemini_client_initialized")

    return await _respond_with_mcp(
        client=client,
        user_message=user_message,
        model=model,
        conversation_history=conversation_history,
        product_results=product_results,
        product_search_performed=product_search_performed,
        product_search_loader=product_search_loader,
        on_text_delta=on_text_delta,
        on_stage=on_stage,
        user_id=user_id,
    )


async def _respond_with_session(
    session: ClientSession | None,
    client: Any,
    user_message: str,
    model: str,
    conversation_history: list[dict[str, Any]],
    product_results: list[dict[str, Any]] | None,
    product_search_performed: list[bool] | None,
    product_search_loader: Callable[[], ContextManager[Any]] | None,
    on_text_delta: Callable[[str], None] | None,
    on_stage: Callable[[str], None] | None,
    user_id: str | None = None,
) -> str:
    return await respond(
        session=session,
        client=client,
        user_message=user_message,
        model=model,
        conversation_history=conversation_history,
        product_results=product_results,
        product_search_performed=product_search_performed,
        product_search_loader=product_search_loader,
        on_text_delta=on_text_delta,
        on_stage=on_stage,
    )


async def _respond_with_mcp(
    client: Any,
    user_message: str,
    model: str,
    conversation_history: list[dict[str, Any]],
    product_results: list[dict[str, Any]] | None,
    product_search_performed: list[bool] | None,
    product_search_loader: Callable[[], ContextManager[Any]] | None,
    on_text_delta: Callable[[str], None] | None,
    on_stage: Callable[[str], None] | None,
    user_id: str | None = None,
) -> str:
    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp.mcp_server"],
        cwd=str(PROJECT_ROOT),
        env={
            "SHOPWISE_CHAT_TIMING": os.getenv(
                "SHOPWISE_CHAT_TIMING",
                "",
            ),
            "SHOPWISE_USER_ID": user_id or "",
        },
    )
    if on_stage is not None:
        on_stage("mcp_process_starting")

    async with stdio_client(server_parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            if on_stage is not None:
                on_stage("mcp_session_initializing")
            await session.initialize()
            if on_stage is not None:
                on_stage("mcp_session_initialized")
            return await _respond_with_session(
                session=session,
                client=client,
                user_message=user_message,
                model=model,
                conversation_history=conversation_history,
                product_results=product_results,
                product_search_performed=product_search_performed,
                product_search_loader=product_search_loader,
                on_text_delta=on_text_delta,
                on_stage=on_stage,
            )
