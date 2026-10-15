import asyncio
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT = (
    "You are a helpful shopping assistant. Search the product catalog using the "
    "available tools before making product recommendations. Treat a stated budget "
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
_BUDGET_INTENT = re.compile(r"\b(?:budget|afford\w*)\b", re.IGNORECASE)
_BUDGET_AMOUNT = re.compile(
    r"(?:₹|rs\.?|inr)\s*\d"
    r"|\b(?:budget|afford\w*)\D{0,24}\d"
    r"|\b(?:under|below|up to|less than|maximum|max)\D{0,12}\d",
    re.IGNORECASE,
)
_BUDGET_CLARIFICATION = "What is your maximum budget in rupees?"


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


def _needs_budget_clarification(message: str) -> bool:
    return bool(
        _BUDGET_INTENT.search(message) and not _BUDGET_AMOUNT.search(message)
    )


def _format_product_results(products: list[dict[str, Any]]) -> str:
    if not products:
        return "Catalog results from shopping.db:\nNo matching products found."

    lines = ["Catalog results from shopping.db:"]
    for product in products:
        price = product.get("price")
        price_text = (
            f"₹{price:,.2f}"
            if isinstance(price, (int, float)) and not isinstance(price, bool)
            else "unavailable"
        )
        rating = product.get("rating_avg")
        rating_text = f"{rating}/5" if rating is not None else "unrated"
        stock = product.get("stock")
        availability = (
            f"In stock ({stock})"
            if isinstance(stock, (int, float)) and stock > 0
            else "Out of stock"
        )
        brand = product.get("brand") or "—"
        category = product.get("category") or "—"
        lines.append(
            f"- {product.get('name') or 'Unnamed product'} | {price_text} | "
            f"Rating: {rating_text} | {availability} | "
            f"Brand: {brand} | Category: {category}"
        )
    return "\n".join(lines)


async def respond(
    session: Any,
    client: Any,
    user_message: str,
    model: str,
    max_tool_rounds: int = 8,
    conversation_history: list[dict[str, Any]] | None = None,
) -> str:
    """Ask Gemini for a response, executing any MCP tools it requests."""
    if max_tool_rounds < 1:
        raise ValueError("max_tool_rounds must be at least 1")

    if not conversation_history and _needs_budget_clarification(user_message):
        if conversation_history is not None:
            conversation_history.extend(
                [
                    {
                        "type": "user_input",
                        "content": [{"type": "text", "text": user_message}],
                    },
                    {
                        "type": "model_output",
                        "content": [
                            {"type": "text", "text": _BUDGET_CLARIFICATION}
                        ],
                    },
                ]
            )
        return _BUDGET_CLARIFICATION

    discovered_tools = await session.list_tools()
    tools = _gemini_tools(discovered_tools.tools)
    product_result_sections: list[str] = []
    history = list(conversation_history or [])
    history.append(
        {
            "type": "user_input",
            "content": [{"type": "text", "text": user_message}],
        }
    )

    for round_number in range(max_tool_rounds + 1):
        interaction = await client.interactions.create(
            model=model,
            input=list(history),
            tools=tools or None,
            system_instruction=SYSTEM_PROMPT,
            store=False,
            timeout=150,
        )
        function_calls = _function_calls(interaction)
        if not function_calls:
            answer = getattr(interaction, "output_text", None) or ""
            if product_result_sections:
                if not answer:
                    answer = "Here are the matching products."
                answer = "\n\n".join(
                    [answer, *product_result_sections]
                ).strip()
            if conversation_history is not None:
                history.extend(
                    _serialize_step(step)
                    for step in (getattr(interaction, "steps", None) or [])
                )
                conversation_history[:] = history
            return answer
        if round_number == max_tool_rounds:
            raise RuntimeError(
                f"Assistant exceeded the limit of {max_tool_rounds} tool-call rounds"
            )

        history.extend(_serialize_step(step) for step in interaction.steps)
        function_responses = []
        for function_call in function_calls:
            arguments = _validate_tool_arguments(
                function_call.name, function_call.arguments
            )
            result = await session.call_tool(function_call.name, arguments)
            if function_call.name == "search_products":
                products = _product_rows(result)
                if products is not None:
                    product_result_sections.append(
                        _format_product_results(products)
                    )
            function_response = {
                "type": "function_result",
                "call_id": function_call.id,
                "name": function_call.name,
                "result": _tool_result_text(result),
            }
            function_responses.append(function_response)

        history.extend(function_responses)

    raise RuntimeError("Assistant stopped without producing a response")


async def chat() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is required. Set it in the environment or in "
            f"{PROJECT_ROOT / '.env'}."
        )

    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server"],
        cwd=str(PROJECT_ROOT),
    )

    async with genai.Client(api_key=api_key).aio as client:
        async with stdio_client(server_parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                conversation_history: list[dict[str, Any]] = []
                print("Shopping assistant ready. Type 'exit' to quit.")
                while True:
                    try:
                        user_message = input("\nYou: ").strip()
                    except (EOFError, KeyboardInterrupt):
                        print()
                        return
                    if user_message.lower() in {"exit", "quit"}:
                        return
                    if not user_message:
                        continue

                    try:
                        answer = await respond(
                            session=session,
                            client=client,
                            user_message=user_message,
                            model=model,
                            conversation_history=conversation_history,
                        )
                    except Exception as error:
                        message = str(error).replace(api_key, "[REDACTED]")
                        message = re.sub(
                            r"(?i)(?:AIza[0-9A-Za-z_-]{20,}|Bearer\s+\S+)",
                            "[REDACTED]",
                            message,
                        )
                        print(
                            f"\nAssistant error ({type(error).__name__}): {message}"
                        )
                        continue
                    print(f"\nAssistant: {answer}")


if __name__ == "__main__":
    asyncio.run(chat())
