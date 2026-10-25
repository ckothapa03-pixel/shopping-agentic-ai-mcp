import asyncio
import re
from contextlib import nullcontext
from typing import Any, Callable, ContextManager

from app.agent.gemini import (
    DEFAULT_GEMINI_TIMEOUT_SECONDS,
    gemini_timeout_seconds,
    request_gemini_interaction,
)
from app.mcp.mcp_tools import (
    call_mcp_tool,
    _function_calls,
    _gemini_tools,
    list_available_tools,
    _product_rows,
    _serialize_step,
    _tool_result_text,
    _validate_tool_arguments,
)

__all__ = [
    "DEFAULT_GEMINI_TIMEOUT_SECONDS",
    "_needs_budget_clarification",
    "chat",
    "gemini_timeout_seconds",
    "is_conversational_only",
    "respond",
]

_BUDGET_INTENT = re.compile(r"\b(?:budget|afford\w*)\b", re.IGNORECASE)

_BUDGET_AMOUNT = re.compile(
    r"(?:₹|rs\.?|inr)\s*\d"
    r"|\b(?:budget|afford\w*)\D{0,24}\d"
    r"|\b(?:under|below|up to|less than|maximum|max)\D{0,12}\d",
    re.IGNORECASE,
)

_BUDGET_CLARIFICATION = "What is your maximum budget in rupees?"

_GREETING_PREFIX = re.compile(
    r"^(?:hi+|hello+|hey+|good\s+(?:morning|afternoon|evening))"
    r"(?:\s+there)?(?:\s*[,;:!?]\s*|\s+|$)",
    re.IGNORECASE,
)

_CONVERSATIONAL_ONLY_MESSAGES = {
    "hi",
    "hii",
    "hiii",
    "hello",
    "hey",
    "hey there",
    "good morning",
    "good afternoon",
    "good evening",
    "how are you",
    "how are you doing",
    "hows it going",
    "whats up",
    "thanks",
    "thank you",
    "thanks thats helpful",
    "thank you thats helpful",
    "okay",
    "ok",
    "great",
    "okay thanks",
    "ok thanks",
    "who are you",
    "who are you and what can you do",
    "what can you do",
    "what can you do for me",
    "how can you help",
    "how can you help me",
    "what is shopwise",
    "what does shopwise do",
    "how does shopwise work",
    "tell me about shopwise",
}

def _needs_budget_clarification(message: str) -> bool:
    return bool(
        _BUDGET_INTENT.search(message) and not _BUDGET_AMOUNT.search(message)
    )

def _is_conversational_only(message: str) -> bool:
    normalized = message.casefold().replace("’", "'").strip()
    normalized = _GREETING_PREFIX.sub("", normalized, count=1).strip()
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = " ".join(normalized.split())
    return not normalized or normalized in _CONVERSATIONAL_ONLY_MESSAGES

def is_conversational_only(message: str) -> bool:
    """Return whether a message is conversational and needs no catalog tools."""
    return _is_conversational_only(message)

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
    product_results: list[dict[str, Any]] | None = None,
    product_search_performed: list[bool] | None = None,
    product_search_loader: Callable[[], ContextManager[Any]] | None = None,
    on_text_delta: Callable[[str], None] | None = None,
    on_stage: Callable[[str], None] | None = None,
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

    is_conversational_only = _is_conversational_only(user_message)
    mcp_tools = (
        []
        if is_conversational_only
        else await list_available_tools(session)
    )
    tools = _gemini_tools(mcp_tools)
    product_result_sections: list[str] = []
    history = list(conversation_history or [])
    history.append(
        {
            "type": "user_input",
            "content": [{"type": "text", "text": user_message}],
        }
    )

    for round_number in range(max_tool_rounds + 1):
        stream_text = on_text_delta is not None and not tools
        interaction = await request_gemini_interaction(
            client,
            model=model,
            history=history,
            tools=tools,
            stream_text=stream_text,
            on_text_delta=on_text_delta,
            on_stage=on_stage,
        )
        requested_calls = _function_calls(interaction)
        function_calls = requested_calls
        if is_conversational_only:
            function_calls = [
                call
                for call in requested_calls
                if getattr(call, "name", None) != "search_products"
            ]
        if requested_calls and not function_calls:
            answer = getattr(interaction, "output_text", None) or (
                "I'm here to help with Shopwise. What would you like to know?"
            )
            if conversation_history is not None:
                history.append(
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": answer}],
                    }
                )
                conversation_history[:] = history
            return answer
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
            search_context = (
                product_search_loader()
                if function_call.name == "search_products"
                and product_search_loader is not None
                else nullcontext()
            )
            with search_context:
                result = await call_mcp_tool(
                    session,
                    function_call.name,
                    arguments,
                )
            if function_call.name == "search_products":
                if product_search_performed is not None:
                    product_search_performed.append(True)
                products = _product_rows(result)
                if products is not None:
                    if product_results is not None:
                        product_results.extend(products)
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
    from app.agent.agent_cli import chat as run_chat

    await run_chat()


if __name__ == "__main__":
    asyncio.run(chat())
