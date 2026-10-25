import logging
import os
from types import SimpleNamespace
from typing import Any, Callable

DEFAULT_GEMINI_TIMEOUT_SECONDS = 90

MIN_GEMINI_TIMEOUT_SECONDS = 5

MAX_GEMINI_TIMEOUT_SECONDS = 300

SYSTEM_PROMPT = (
    "You are a helpful shopping assistant. Respond naturally to ordinary "
    "greetings without searching the product catalog or making product claims. "
    "Use the product search tool only when the shopper asks about specific "
    "products, recommendations, or catalog availability. Search the product "
    "catalog using the available tools before making product recommendations. "
    "Treat a stated budget "
    "as a maximum price and pass it as max_price to search_products. If a shopper "
    "asks to find products within a budget but does not state an amount, ask only "
    "for their maximum budget in rupees and do not search yet. Do not ask for a "
    "product category unless the shopper requests category-specific results. "
    "Respect the shopper's "
    "filters, and clearly state when no matching products are found. "
    "The application appends a verified product list with names, prices, ratings, "
    "stock availability, brands, and categories. After searching, give only a "
    "brief natural-language summary and do not repeat the product list. Do not "
    "invent product details."
)

def gemini_timeout_seconds() -> int:
    """Return the bounded Gemini request timeout from the environment."""
    raw_timeout = os.getenv("GEMINI_TIMEOUT_SECONDS")
    if raw_timeout is None:
        return DEFAULT_GEMINI_TIMEOUT_SECONDS
    try:
        timeout = int(raw_timeout)
    except (TypeError, ValueError):
        logging.getLogger(__name__).warning(
            "Ignoring invalid GEMINI_TIMEOUT_SECONDS; using the default."
        )
        return DEFAULT_GEMINI_TIMEOUT_SECONDS
    if not MIN_GEMINI_TIMEOUT_SECONDS <= timeout <= MAX_GEMINI_TIMEOUT_SECONDS:
        logging.getLogger(__name__).warning(
            "GEMINI_TIMEOUT_SECONDS must be between %s and %s; using the default.",
            MIN_GEMINI_TIMEOUT_SECONDS,
            MAX_GEMINI_TIMEOUT_SECONDS,
        )
        return DEFAULT_GEMINI_TIMEOUT_SECONDS
    return timeout

class GeminiStreamError(RuntimeError):
    """Sanitized streaming failure carrying only an optional HTTP status."""

    def __init__(self, status_code: int | None = None) -> None:
        super().__init__("Gemini streaming response failed")
        self.status_code = status_code


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)

def _output_text_from_steps(steps: list[Any]) -> str:
    text_parts: list[str] = []
    for step in steps:
        if _field(step, "type") != "model_output":
            continue
        for content in _field(step, "content", []) or []:
            if _field(content, "type") == "text":
                text = _field(content, "text", "")
                if text:
                    text_parts.append(text)
    return "".join(text_parts)

async def _consume_interaction_stream(
    stream: Any,
    on_text_delta: Callable[[str], None],
    on_stage: Callable[[str], None] | None = None,
) -> Any:
    """Collect streamed Gemini text and return the completed interaction shape."""
    if not hasattr(stream, "__aiter__"):
        # Allows SDK-compatible adapters and test doubles to return a completed
        # Interaction even when streaming was requested.
        return stream

    text_parts: list[str] = []
    completed_interaction = None
    first_event_seen = False
    async for event in stream:
        if not first_event_seen:
            first_event_seen = True
            if on_stage is not None:
                on_stage("first_stream_event_received")
        event_type = _field(event, "event_type")
        if event_type == "error":
            error = _field(event, "error")
            code = _field(error, "code")
            raise GeminiStreamError(code if isinstance(code, int) else None)
        if event_type == "step.delta":
            delta = _field(event, "delta")
            if _field(delta, "type") == "text":
                text = _field(delta, "text", "")
                if text:
                    text_parts.append(text)
                    on_text_delta(text)
        elif event_type == "interaction.completed":
            completed_interaction = _field(event, "interaction")

    if completed_interaction is None:
        raise RuntimeError("Gemini streaming response ended before completion")
    status = _field(completed_interaction, "status")
    if status not in (None, "completed"):
        raise RuntimeError("Gemini could not complete the response")

    steps = _field(completed_interaction, "steps", []) or []
    answer = "".join(text_parts) or _output_text_from_steps(steps)
    if answer and not steps:
        steps = [
            {
                "type": "model_output",
                "content": [{"type": "text", "text": answer}],
            }
        ]
    return SimpleNamespace(steps=steps, output_text=answer)


async def request_gemini_interaction(
    client: Any,
    *,
    model: str,
    history: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    stream_text: bool,
    on_text_delta: Callable[[str], None] | None,
    on_stage: Callable[[str], None] | None,
) -> Any:
    if on_stage is not None:
        on_stage("gemini_request_started")
    response = await client.interactions.create(
        model=model,
        input=list(history),
        tools=tools or None,
        system_instruction=SYSTEM_PROMPT,
        store=False,
        timeout=gemini_timeout_seconds(),
        **({"stream": True} if stream_text else {}),
    )
    if on_stage is not None:
        on_stage("gemini_stream_opened" if stream_text else "gemini_response_received")
    if stream_text and on_text_delta is not None:
        return await _consume_interaction_stream(response, on_text_delta, on_stage)
    return response
