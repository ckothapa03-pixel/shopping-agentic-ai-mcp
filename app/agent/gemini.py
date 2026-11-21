import os
import sys
import time
from typing import Any, Callable

from app.agent.gemini_config import (
    DEFAULT_GEMINI_TIMEOUT_SECONDS,
    gemini_timeout_seconds,
)
from app.agent.gemini_prompt import SYSTEM_PROMPT
from app.agent.gemini_stream import GeminiStreamError, consume_interaction_stream


async def request_gemini_interaction(
    client: Any,
    *,
    model: str,
    history: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    request_number: int = 1,
    stream_text: bool,
    on_text_delta: Callable[[str], None] | None,
    on_stage: Callable[[str], None] | None,
) -> Any:
    started_at = time.perf_counter()
    outcome = "failed"
    if on_stage:
        on_stage("gemini_request_started")
    try:
        response = await client.interactions.create(
            model=model,
            input=list(history),
            tools=tools or None,
            system_instruction=SYSTEM_PROMPT,
            store=False,
            timeout=gemini_timeout_seconds(),
            **({"stream": True} if stream_text else {}),
        )
        if on_stage:
            on_stage("gemini_stream_opened" if stream_text else "gemini_response_received")
        if stream_text and on_text_delta:
            response = await consume_interaction_stream(
                response,
                on_text_delta,
                on_stage,
            )
        outcome = "completed"
        return response
    finally:
        if os.getenv("SHOPWISE_CHAT_TIMING", "").strip().casefold() in {
            "1", "true", "yes", "on",
        }:
            elapsed = time.perf_counter() - started_at
            print(
                "Shopwise chat timing "
                f"stage=gemini_request request={request_number} "
                f"outcome={outcome} elapsed_seconds={elapsed:.3f}",
                file=sys.stderr,
                flush=True,
            )


__all__ = [
    "DEFAULT_GEMINI_TIMEOUT_SECONDS",
    "GeminiStreamError",
    "gemini_timeout_seconds",
    "request_gemini_interaction",
]
