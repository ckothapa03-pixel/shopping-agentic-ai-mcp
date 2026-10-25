import json
import math
from datetime import timedelta
from typing import Any

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
    return await session.call_tool(
        name,
        arguments,
        read_timeout_seconds=timedelta(seconds=PRODUCT_TOOL_TIMEOUT_SECONDS),
    )


def _gemini_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        }
        for tool in mcp_tools
    ]

def _function_calls(interaction: Any) -> list[Any]:
    return [
        step
        for step in (getattr(interaction, "steps", None) or [])
        if getattr(step, "type", None) == "function_call"
    ]

def _tool_result_text(result: Any) -> str:
    if result.isError:
        details = "\n".join(
            block.text for block in result.content if hasattr(block, "text")
        )
        raise RuntimeError(f"MCP tool call failed: {details or 'unknown error'}")

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
