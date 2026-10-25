import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.agent.agent import respond

PROJECT_ROOT = Path(__file__).resolve().parents[2]

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
        args=["-m", "app.mcp.mcp_server"],
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
