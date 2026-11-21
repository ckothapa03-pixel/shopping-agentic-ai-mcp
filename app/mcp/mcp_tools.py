import json
import logging
import math
import os
import time
from datetime import timedelta
from typing import Any

from app.agent.tool_permissions import require_autonomous_permission
from app.observability import log_failure

PRODUCT_TOOL_TIMEOUT_SECONDS = 30

__all__ = [
    "PRODUCT_TOOL_TIMEOUT_SECONDS",
    "_function_calls",
    "_gemini_tools",
    "_product_rows",
    "_serialize_step",
    "_tool_result_text",
    "_validate_tool_arguments",
    "call_mcp_tool",
    "list_available_tools",
]


async def list_available_tools(session: Any) -> list[Any]:
    return (await session.list_tools()).tools


async def call_mcp_tool(
    session: Any,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    require_autonomous_permission(name)
    started_at = time.perf_counter()
    outcome = "failed"
    try:
        result = await session.call_tool(
            name,
            arguments,
            read_timeout_seconds=timedelta(seconds=PRODUCT_TOOL_TIMEOUT_SECONDS),
        )
        outcome = "completed"
        return result
    finally:
        if os.getenv("SHOPWISE_CHAT_TIMING", "").strip().casefold() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            elapsed = time.perf_counter() - started_at
            logging.getLogger("app.mcp").debug(
                "Shopwise chat timing "
                f"stage=mcp_tool name={name} outcome={outcome} "
                f"elapsed_seconds={elapsed:.3f}"
            )


def _gemini_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    from app.agent.tool_permissions import filter_autonomous_tools

    return filter_autonomous_tools(mcp_tools)

def _function_calls(interaction: Any) -> list[Any]:
    return [
        step
        for step in (getattr(interaction, "steps", None) or [])
        if getattr(step, "type", None) == "function_call"
    ]

def _tool_result_text(result: Any) -> str:
    if result.isError:
        error = RuntimeError("MCP tool call failed")
        log_failure("mcp_tool_failed", error)
        raise RuntimeError("The shopping assistant could not complete this request.") from None

    structured_content = getattr(result, "structuredContent", None)
    if structured_content is not None:
        return json.dumps(structured_content, ensure_ascii=False)

    return "\n".join(
        block.text for block in result.content if hasattr(block, "text")
    )

def _product_rows(result: Any) -> list[dict[str, Any]] | None:
    structured_content = getattr(result, "structuredContent", None)
    if isinstance(structured_content, dict):
        rows = structured_content.get("result")
    else:
        rows = structured_content

    if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
        return rows
    return None

def _serialize_step(step: Any) -> dict[str, Any]:
    if isinstance(step, dict):
        return step
    model_dump = getattr(step, "model_dump", None)
    if not callable(model_dump):
        raise TypeError("Gemini returned a conversation step that cannot be serialized")
    return model_dump(exclude_none=True)

def _validate_tool_arguments(name: str, arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise ValueError(f"Model arguments for {name} must be an object")
    if name == "search_products" and "max_price" in arguments:
        max_price = arguments["max_price"]
        if (
            isinstance(max_price, bool)
            or not isinstance(max_price, (int, float))
            or not math.isfinite(max_price)
            or max_price < 0
        ):
            raise ValueError(
                "Model supplied an invalid max_price; expected a non-negative number"
            )
    return arguments
