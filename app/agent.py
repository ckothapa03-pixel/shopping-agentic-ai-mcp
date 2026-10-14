import asyncio
import json
import os
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
    "available tools before making product recommendations. Respect the shopper's "
    "filters, and clearly state when no matching products are found."
)


def _gemini_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    if not mcp_tools:
        return []
    return [
        {
            "function_declarations": [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                }
                for tool in mcp_tools
            ]
        }
    ]


def _tool_calls(response: Any) -> list[Any]:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        raise RuntimeError("Gemini returned no response candidates")
    content = getattr(candidates[0], "content", None)
    return [
        part.function_call
        for part in getattr(content, "parts", [])
        if getattr(part, "function_call", None) is not None
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


async def respond(
    session: Any,
    client: Any,
    user_message: str,
    model: str,
    max_tool_rounds: int = 8,
) -> str:
    """Ask Gemini for a response, executing any MCP tools it requests."""
    if max_tool_rounds < 1:
        raise ValueError("max_tool_rounds must be at least 1")

    discovered_tools = await session.list_tools()
    tools = _gemini_tools(discovered_tools.tools)
    contents: list[Any] = [
        {"role": "user", "parts": [{"text": user_message}]},
    ]
    config: dict[str, Any] = {"system_instruction": SYSTEM_PROMPT}
    if tools:
        config["tools"] = tools

    for round_number in range(max_tool_rounds + 1):
        response = await client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        function_calls = _tool_calls(response)
        if not function_calls:
            return getattr(response, "text", None) or ""
        if round_number == max_tool_rounds:
            raise RuntimeError(
                f"Assistant exceeded the limit of {max_tool_rounds} tool-call rounds"
            )

        contents.append(response.candidates[0].content)
        function_responses = []
        for function_call in function_calls:
            arguments = function_call.args
            if not isinstance(arguments, dict):
                raise ValueError(
                    f"Model arguments for {function_call.name} must be an object"
                )

            result = await session.call_tool(function_call.name, arguments)
            function_responses.append(
                {
                    "function_response": {
                        "name": function_call.name,
                        "response": {"result": _tool_result_text(result)},
                    }
                }
            )

        contents.append({"role": "user", "parts": function_responses})

    raise RuntimeError("Assistant stopped without producing a response")


async def chat() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is required. Set it in the environment or in "
            f"{PROJECT_ROOT / '.env'}."
        )

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server"],
        cwd=str(PROJECT_ROOT),
    )

    async with genai.Client(api_key=api_key).aio as client:
        async with stdio_client(server_parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
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

                    answer = await respond(
                        session=session,
                        client=client,
                        user_message=user_message,
                        model=model,
                    )
                    print(f"\nAssistant: {answer}")


if __name__ == "__main__":
    asyncio.run(chat())
