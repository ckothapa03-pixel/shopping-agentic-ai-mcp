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
            type="function_call",
            id="call-1",
            name="search_products",
            arguments={"search_term": "wireless mouse"},
            model_dump=lambda **_: {
                "type": "function_call",
                "id": "call-1",
                "name": "search_products",
                "arguments": {"search_term": "wireless mouse"},
            },
        )
        tool_call_response = SimpleNamespace(
            steps=[function_call],
            output_text="",
        )
        final_response = SimpleNamespace(
            steps=[SimpleNamespace(type="model_output")],
            output_text="I found a mouse.",
        )
        client = SimpleNamespace(
            interactions=SimpleNamespace(
                create=AsyncMock(
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
        first_request = client.interactions.create.await_args_list[0].kwargs
        self.assertEqual(
            first_request["tools"][0]["name"],
            "search_products",
        )
        self.assertEqual(first_request["store"], False)
        second_request = client.interactions.create.await_args_list[1].kwargs
        self.assertEqual(
            second_request["input"][0]["type"],
            "user_input",
        )
        self.assertEqual(
            second_request["input"][0]["content"][0]["text"],
            "Find a wireless mouse",
        )
        self.assertEqual(
            second_request["input"][-1]["type"],
            "function_result",
        )
        self.assertEqual(
            second_request["input"][-1]["call_id"],
            "call-1",
        )
        self.assertEqual(
            second_request["input"][-1]["result"],
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
            type="function_call",
            id="call-1",
            name="search_products",
            arguments={},
            model_dump=lambda **_: {
                "type": "function_call",
                "id": "call-1",
                "name": "search_products",
                "arguments": {},
            },
        )
        tool_call_response = SimpleNamespace(
            steps=[function_call],
            output_text="",
        )
        client = SimpleNamespace(
            interactions=SimpleNamespace(
                create=AsyncMock(
                    return_value=tool_call_response
                )
            )
        )

        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            await respond(session, client, "Search for a mouse", "test-model")


if __name__ == "__main__":
    unittest.main()
