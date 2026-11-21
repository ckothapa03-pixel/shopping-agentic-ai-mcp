import asyncio
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
from app.agent.recommendations import (
    BUDGET_CLARIFICATION,
    format_product_results,
    needs_budget_clarification,
)

__all__ = [
    "DEFAULT_GEMINI_TIMEOUT_SECONDS",
    "_needs_budget_clarification",
    "chat",
    "gemini_timeout_seconds",
    "respond",
]

def _needs_budget_clarification(message: str) -> bool:
    return needs_budget_clarification(message)

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
                            {"type": "text", "text": BUDGET_CLARIFICATION}
                        ],
                    },
                ]
            )
        return BUDGET_CLARIFICATION

    if on_stage is not None:
        on_stage("mcp_tool_discovery_started")
    mcp_tools = await list_available_tools(session)
    if on_stage is not None:
        on_stage("mcp_tool_discovery_completed")
    tools = _gemini_tools(mcp_tools)
    product_result_sections: list[str] = []
    history = list(conversation_history or [])
    history.append(
        {
            "type": "user_input",
            "content": [{"type": "text", "text": user_message}],
        }
    )

    request_number = 0
    for round_number in range(max_tool_rounds + 1):
        stream_text = on_text_delta is not None
        request_number += 1
        interaction = await request_gemini_interaction(
            client,
            model=model,
            history=history,
            tools=tools,
            request_number=request_number,
            stream_text=stream_text,
            on_text_delta=on_text_delta,
            on_stage=on_stage,
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
                        format_product_results(products)
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
