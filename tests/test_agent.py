import json
import os
import sys
import unittest
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.agent.agent import _needs_budget_clarification, respond


class _TrackedLoader:
    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0
        self.active = False

    @contextmanager
    def __call__(self):
        self.entered += 1
        self.active = True
        try:
            yield
        finally:
            self.active = False
            self.exited += 1


class _AsyncEventStream:
    def __init__(self, events) -> None:
        self.events = events

    def __aiter__(self):
        self._iterator = iter(self.events)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration:
            raise StopAsyncIteration


class ShoppingAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_gemini_timeout_is_configurable_and_passed_to_interactions(self) -> None:
        interaction = SimpleNamespace(steps=[], output_text="Hello!")
        client = SimpleNamespace(
            interactions=SimpleNamespace(create=AsyncMock(return_value=interaction))
        )
        with patch.dict(os.environ, {"GEMINI_TIMEOUT_SECONDS": "17"}):
            answer = await respond(None, client, "Hello", "test-model")

        self.assertEqual(answer, "Hello!")
        self.assertEqual(client.interactions.create.await_args.kwargs["timeout"], 17)

    async def test_greeting_is_answered_by_gemini_without_product_tool_call(self) -> None:
        session = SimpleNamespace(
            list_tools=AsyncMock(return_value=SimpleNamespace(tools=[])),
            call_tool=AsyncMock(),
        )
        interaction = SimpleNamespace(
            steps=[SimpleNamespace(type="model_output")],
            output_text="Hello! How can I help you today?",
        )
        client = SimpleNamespace(
            interactions=SimpleNamespace(create=AsyncMock(return_value=interaction))
        )
        loader = _TrackedLoader()

        answer = await respond(
            session,
            client,
            "Hii",
            "test-model",
            product_search_loader=loader,
        )

        self.assertEqual(answer, "Hello! How can I help you today?")
        session.list_tools.assert_not_awaited()
        session.call_tool.assert_not_awaited()
        self.assertEqual((loader.entered, loader.exited, loader.active), (0, 0, False))
        client.interactions.create.assert_awaited_once()

    async def test_streams_gemini_text_deltas_without_starting_mcp(self) -> None:
        session = SimpleNamespace(
            list_tools=AsyncMock(),
            call_tool=AsyncMock(),
        )
        output_step = SimpleNamespace(
            type="model_output",
            model_dump=lambda **_: {
                "type": "model_output",
                "content": [{"type": "text", "text": "Hello there!"}],
            },
        )
        client = SimpleNamespace(
            interactions=SimpleNamespace(
                create=AsyncMock(
                    return_value=_AsyncEventStream(
                        [
                            SimpleNamespace(
                                event_type="step.delta",
                                delta=SimpleNamespace(type="text", text="Hello "),
                            ),
                            SimpleNamespace(
                                event_type="step.delta",
                                delta=SimpleNamespace(type="text", text="there!"),
                            ),
                            SimpleNamespace(
                                event_type="interaction.completed",
                                interaction=SimpleNamespace(
                                    status="completed",
                                    steps=[output_step],
                                ),
                            ),
                        ]
                    )
                )
            )
        )
        streamed_chunks: list[str] = []
        history: list[dict[str, object]] = []

        answer = await respond(
            session,
            client,
            "Hello",
            "test-model",
            conversation_history=history,
            on_text_delta=streamed_chunks.append,
        )

        self.assertEqual(answer, "Hello there!")
        self.assertEqual(streamed_chunks, ["Hello ", "there!"])
        self.assertEqual(
            history[-1],
            {
                "type": "model_output",
                "content": [{"type": "text", "text": "Hello there!"}],
            },
        )
        session.list_tools.assert_not_awaited()
        session.call_tool.assert_not_awaited()
        client.interactions.create.assert_awaited_once()
        self.assertTrue(client.interactions.create.await_args.kwargs["stream"])

    async def test_ordinary_conversation_is_handled_by_gemini_without_search(self) -> None:
        messages = [
            "Hi",
            "Hii!!",
            "Hello",
            "Hey",
            "Hey there",
            "Good morning",
            "Good afternoon",
            "Good evening",
            "How are you?",
            "How's it going?",
            "What's up?",
            "Thanks, that's helpful.",
            "Thank you",
            "Okay",
            "Great",
            "Who are you and what can you do?",
            "How can you help me?",
            "What is Shopwise?",
        ]
        search_tool = SimpleNamespace(
            name="search_products",
            description="Search the product catalog",
            inputSchema={"type": "object", "properties": {}},
        )
        for index, message in enumerate(messages):
            with self.subTest(message=message):
                session = SimpleNamespace(
                    list_tools=AsyncMock(
                        return_value=SimpleNamespace(tools=[search_tool])
                    ),
                    call_tool=AsyncMock(),
                )
                answer_text = f"Gemini response {index} to {message}"
                interaction = SimpleNamespace(
                    steps=[SimpleNamespace(type="model_output")],
                    output_text=answer_text,
                )
                client = SimpleNamespace(
                    interactions=SimpleNamespace(
                        create=AsyncMock(return_value=interaction)
                    )
                )

                answer = await respond(session, client, message, "test-model")

                self.assertEqual(answer, answer_text)
                session.list_tools.assert_not_awaited()
                session.call_tool.assert_not_awaited()
                client.interactions.create.assert_awaited_once()
                self.assertIsNone(
                    client.interactions.create.await_args.kwargs["tools"]
                )

    async def test_discovers_and_calls_mcp_tool_then_returns_answer(self) -> None:
        tool = SimpleNamespace(
            name="search_products",
            description="Search the product catalog",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {"type": "string"},
                    "max_price": {"type": "number"},
                },
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
            arguments={"search_term": "mouse", "max_price": 1000},
            model_dump=lambda **_: {
                "type": "function_call",
                "id": "call-1",
                "name": "search_products",
                "arguments": {"search_term": "mouse", "max_price": 1000},
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

        user_message = "Hi, find me a mouse under ₹1000"
        product_rows: list[dict[str, object]] = []
        searched: list[bool] = []
        loader = _TrackedLoader()
        answer = await respond(
            session,
            client,
            user_message,
            "test-model",
            product_results=product_rows,
            product_search_performed=searched,
            product_search_loader=loader,
        )

        self.assertTrue(answer.startswith("I found a mouse."))
        self.assertIn(
            "- Wireless mouse | ₹25.00 | Rating: unrated | Out of stock | "
            "Brand: — | Category: —",
            answer,
        )
        session.list_tools.assert_awaited_once()
        session.call_tool.assert_awaited_once_with(
            "search_products",
            {"search_term": "mouse", "max_price": 1000},
            read_timeout_seconds=timedelta(seconds=30),
        )
        self.assertEqual(product_rows, [{"name": "Wireless mouse", "price": 25}])
        self.assertEqual(searched, [True])
        self.assertEqual((loader.entered, loader.exited, loader.active), (1, 1, False))
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
            user_message,
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

        loader = _TrackedLoader()
        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            await respond(
                session,
                client,
                "Search for a mouse",
                "test-model",
                product_search_loader=loader,
            )
        self.assertEqual((loader.entered, loader.exited, loader.active), (1, 1, False))

    async def test_detects_missing_budget_and_requests_only_the_amount(self) -> None:
        user_story = (
            "As a shopper, I want to search for products within my budget "
            "so that I can find affordable products easily."
        )
        self.assertTrue(_needs_budget_clarification(user_story))
        self.assertFalse(_needs_budget_clarification("Budget of ₹1,000"))
        self.assertFalse(_needs_budget_clarification("Find products under 1000"))

        session = SimpleNamespace(
            list_tools=AsyncMock(),
            call_tool=AsyncMock(),
        )
        client = SimpleNamespace(interactions=SimpleNamespace(create=AsyncMock()))
        conversation_history: list[dict[str, object]] = []
        answer = await respond(
            session,
            client,
            user_story,
            "test-model",
            conversation_history=conversation_history,
        )

        self.assertEqual(answer, "What is your maximum budget in rupees?")
        session.list_tools.assert_not_awaited()
        client.interactions.create.assert_not_awaited()
        self.assertEqual(conversation_history[0]["content"][0]["text"], user_story)
        self.assertEqual(
            conversation_history[1]["content"][0]["text"],
            "What is your maximum budget in rupees?",
        )

    async def test_budget_request_calls_real_mcp_tool_and_formats_database_rows(
        self,
    ) -> None:
        user_story = (
            "As a shopper, I want to search for products within my budget "
            "so that I can find affordable products easily."
        )
        user_budget = "1000"
        function_call = SimpleNamespace(
            type="function_call",
            id="budget-call",
            name="search_products",
            arguments={"max_price": 1000},
            model_dump=lambda **_: {
                "type": "function_call",
                "id": "budget-call",
                "name": "search_products",
                "arguments": {"max_price": 1000},
            },
        )
        client = SimpleNamespace(
            interactions=SimpleNamespace(
                create=AsyncMock(
                    side_effect=[
                        SimpleNamespace(steps=[function_call], output_text=""),
                        SimpleNamespace(
                            steps=[
                                SimpleNamespace(
                                    type="model_output",
                                    model_dump=lambda **_: {
                                        "type": "model_output",
                                        "content": [
                                            {
                                                "type": "text",
                                                "text": "I found affordable products.",
                                            }
                                        ],
                                    },
                                )
                            ],
                            output_text="Here are affordable products.",
                        ),
                    ]
                )
            )
        )
        project_root = Path(__file__).resolve().parent.parent
        server_parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp.mcp_server"],
            cwd=str(project_root),
        )

        async with stdio_client(server_parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                real_list_tools = session.list_tools
                session.list_tools = AsyncMock(wraps=real_list_tools)
                real_call_tool = session.call_tool
                session.call_tool = AsyncMock(wraps=real_call_tool)
                conversation_history: list[dict[str, object]] = []
                clarification_answer = await respond(
                    session,
                    client,
                    user_story,
                    "test-model",
                    conversation_history=conversation_history,
                )
                self.assertIn("maximum budget", clarification_answer)
                session.list_tools.assert_not_awaited()
                session.call_tool.assert_not_awaited()
                answer = await respond(
                    session,
                    client,
                    user_budget,
                    "test-model",
                    conversation_history=conversation_history,
                )

        session.call_tool.assert_awaited_once_with(
            "search_products",
            {"max_price": 1000},
            read_timeout_seconds=timedelta(seconds=30),
        )
        session.list_tools.assert_awaited_once()
        tool_call_request = client.interactions.create.await_args_list[0].kwargs
        self.assertEqual(
            tool_call_request["input"][0]["content"][0]["text"],
            user_story,
        )
        self.assertEqual(
            tool_call_request["input"][-1]["content"][0]["text"],
            user_budget,
        )
        self.assertEqual(
            tool_call_request["input"][1]["content"][0]["text"],
            "What is your maximum budget in rupees?",
        )
        final_request = client.interactions.create.await_args_list[1].kwargs
        tool_result = final_request["input"][-1]
        self.assertEqual(tool_result["type"], "function_result")
        database_result = json.loads(tool_result["result"])
        products = database_result["result"]
        self.assertTrue(products)
        self.assertTrue(all(product["price"] <= 1000 for product in products))
        for field in ("name", "price", "rating_avg", "stock", "brand", "category"):
            self.assertTrue(all(field in product for product in products))
        for product in products:
            self.assertIn(product["name"], answer)
            self.assertIn(f"₹{product['price']:,.2f}", answer)
            self.assertIn(f"Rating: {product['rating_avg']}/5", answer)
            self.assertIn(
                "Out of stock" if product["stock"] == 0 else "In stock",
                answer,
            )
            self.assertIn(f"Brand: {product['brand']}", answer)
            self.assertIn(f"Category: {product['category']}", answer)
        self.assertIn("Catalog results from shopping.db:", answer)
        self.assertIn("Here are affordable products.", answer)

    async def test_rejects_malformed_budget_arguments_without_calling_tool(
        self,
    ) -> None:
        session = SimpleNamespace(
            list_tools=AsyncMock(return_value=SimpleNamespace(tools=[])),
            call_tool=AsyncMock(),
        )
        function_call = SimpleNamespace(
            type="function_call",
            id="bad-budget-call",
            name="search_products",
            arguments={"max_price": "one thousand"},
            model_dump=lambda **_: {
                "type": "function_call",
                "id": "bad-budget-call",
                "name": "search_products",
                "arguments": {"max_price": "one thousand"},
            },
        )
        client = SimpleNamespace(
            interactions=SimpleNamespace(
                create=AsyncMock(
                    return_value=SimpleNamespace(
                        steps=[function_call],
                        output_text="",
                    )
                )
            )
        )

        with self.assertRaisesRegex(ValueError, "invalid max_price"):
            await respond(session, client, "Budget 1000", "test-model")
        session.call_tool.assert_not_awaited()

    async def test_surfaces_gemini_api_failures(self) -> None:
        session = SimpleNamespace(
            list_tools=AsyncMock(return_value=SimpleNamespace(tools=[])),
            call_tool=AsyncMock(),
        )
        client = SimpleNamespace(
            interactions=SimpleNamespace(
                create=AsyncMock(side_effect=TimeoutError("request timed out"))
            )
        )

        with self.assertRaisesRegex(TimeoutError, "request timed out"):
            await respond(session, client, "Search for a mouse", "test-model")

    async def test_preserves_empty_database_result_message(self) -> None:
        session = SimpleNamespace(
            list_tools=AsyncMock(return_value=SimpleNamespace(tools=[])),
            call_tool=AsyncMock(
                return_value=SimpleNamespace(
                    isError=False,
                    content=[],
                    structuredContent={"result": []},
                )
            ),
        )
        function_call = SimpleNamespace(
            type="function_call",
            id="empty-call",
            name="search_products",
            arguments={"max_price": 0},
            model_dump=lambda **_: {
                "type": "function_call",
                "id": "empty-call",
                "name": "search_products",
                "arguments": {"max_price": 0},
            },
        )
        client = SimpleNamespace(
            interactions=SimpleNamespace(
                create=AsyncMock(
                    side_effect=[
                        SimpleNamespace(steps=[function_call], output_text=""),
                        SimpleNamespace(
                            steps=[
                                SimpleNamespace(
                                    type="model_output",
                                    model_dump=lambda **_: {
                                        "type": "model_output",
                                        "content": [],
                                    },
                                )
                            ],
                            output_text="No affordable products found.",
                        ),
                    ]
                )
            )
        )

        answer = await respond(session, client, "Budget 0", "test-model")
        self.assertIn("No matching products found.", answer)


if __name__ == "__main__":
    unittest.main()
