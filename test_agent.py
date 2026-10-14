import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.agent import respond


class ShoppingAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovers_and_calls_mcp_tool_then_returns_answer(self) -> None:
        tool = SimpleNamespace(
            name="search_products",
            description="Search the product catalog",
            inputSchema={
                "type": "object",
                "properties": {"search_term": {"type": "string"}},
                "required": ["search_term"],
            },
        )
        session = SimpleNamespace(
            list_tools=AsyncMock(return_value=SimpleNamespace(tools=[tool])),
            call_tool=AsyncMock(
                return_value=SimpleNamespace(
                    isError=False,
                    content=[],
                    structuredContent=[{"name": "Wireless mouse", "price": 25}],
                )
            ),
        )
        function_call = SimpleNamespace(
            name="search_products",
            args={"search_term": "wireless mouse"},
        )
        tool_call_response = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[SimpleNamespace(function_call=function_call)]
                    )
                )
            ]
        )
        final_response = SimpleNamespace(
            candidates=[SimpleNamespace(content=SimpleNamespace(parts=[]))],
            text="I found a mouse.",
        )
        client = SimpleNamespace(
            models=SimpleNamespace(
                generate_content=AsyncMock(
                    side_effect=[tool_call_response, final_response]
                )
            )
        )

        answer = await respond(session, client, "Find a wireless mouse", "test-model")

        self.assertEqual(answer, "I found a mouse.")
        session.list_tools.assert_awaited_once()
        session.call_tool.assert_awaited_once_with(
            "search_products", {"search_term": "wireless mouse"}
        )
        first_request = client.models.generate_content.await_args_list[0].kwargs
        declarations = first_request["config"]["tools"][0]["function_declarations"]
        self.assertEqual(declarations[0]["name"], "search_products")
        second_request = client.models.generate_content.await_args_list[1].kwargs
        self.assertEqual(
            second_request["contents"][-1]["parts"][0]["function_response"]["response"][
                "result"
            ],
            '[{"name": "Wireless mouse", "price": 25}]',
        )

    async def test_reports_mcp_tool_errors(self) -> None:
        session = SimpleNamespace(
            list_tools=AsyncMock(return_value=SimpleNamespace(tools=[])),
            call_tool=AsyncMock(
                return_value=SimpleNamespace(
                    isError=True,
                    content=[SimpleNamespace(text="database unavailable")],
                )
            ),
        )
        function_call = SimpleNamespace(
            name="search_products",
            args={},
        )
        tool_call_response = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[SimpleNamespace(function_call=function_call)]
                    )
                )
            ]
        )
        client = SimpleNamespace(
            models=SimpleNamespace(
                generate_content=AsyncMock(
                    return_value=tool_call_response
                )
            )
        )

        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            await respond(session, client, "Search for a mouse", "test-model")


if __name__ == "__main__":
    unittest.main()
