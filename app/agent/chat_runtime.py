import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.agent.agent import is_conversational_only, respond

PROJECT_ROOT = Path(__file__).resolve().parents[2]

__all__ = ["_record_chat_stage", "_respond_with_agent"]

def _record_chat_stage(started_at: float, stage: str) -> None:
    """Print timing-only diagnostics when explicitly enabled for debugging."""
    if os.getenv("SHOPWISE_CHAT_TIMING", "").strip().casefold() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return
    elapsed = time.perf_counter() - started_at
    print(
        f"Shopwise chat timing stage={stage} elapsed_seconds={elapsed:.3f}",
        flush=True,
    )

async def _respond_with_agent(
    user_message: str,
    conversation_history: list[dict[str, Any]],
    product_results: list[dict[str, Any]] | None = None,
    product_search_performed: list[bool] | None = None,
    product_search_loader: Any | None = None,
    on_text_delta: Any | None = None,
    on_stage: Any | None = None,
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
        if on_stage is not None:
            on_stage("gemini_client_initialized")

        conversational_only = is_conversational_only(user_message)

        if on_stage is not None:
            on_stage(
                "greeting_detected"
                if conversational_only
                else "product_request_detected"
            )

        if conversational_only:
            return await respond(
                session=None,
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

        server_parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp.mcp_server"],
            cwd=str(PROJECT_ROOT),
        )

        async with stdio_client(server_parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

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
