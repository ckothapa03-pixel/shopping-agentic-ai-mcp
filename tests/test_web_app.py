import asyncio
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from google.genai._gaos.lib.compat_errors import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)

from app.agent.chat_runtime import PROJECT_ROOT, _respond_with_agent
from app.ui.chat.chat_errors import (
    _chat_error_message,
    _classify_chat_error,
    _log_chat_exception,
)
from app.ui.chat.chat_grounding import ground_chat_answer as _ground_chat_answer


class _AsyncContext:
    def __init__(self, value: object) -> None:
        self.value = value
        self.enter_count = 0
        self.exit_count = 0

    async def __aenter__(self) -> object:
        self.enter_count += 1
        return self.value

    async def __aexit__(self, *_args: object) -> None:
        self.exit_count += 1
        return None


class GroundedChatAnswerTests(unittest.TestCase):
    def test_classifies_timeout_connection_auth_rate_and_api_failures(self) -> None:
        cases = (
            (httpx.ReadTimeout("private timeout text"), "timeout", "timed out"),
            (
                APITimeoutError(httpx.Request("POST", "https://example.invalid")),
                "timeout",
                "timed out",
            ),
            (httpx.ConnectError("private host details"), "connection", "connect to Gemini"),
            (
                APIConnectionError(
                    request=httpx.Request("POST", "https://example.invalid")
                ),
                "connection",
                "connect to Gemini",
            ),
            (
                AuthenticationError(
                    "secret credential detail",
                    response=httpx.Response(
                        401,
                        request=httpx.Request("POST", "https://example.invalid"),
                    ),
                    body={"message": "secret credential detail"},
                ),
                "authentication",
                "rejected the configured credentials",
            ),
            (
                RateLimitError(
                    "private quota details",
                    response=httpx.Response(
                        429,
                        request=httpx.Request("POST", "https://example.invalid"),
                    ),
                    body={"message": "private quota details"},
                ),
                "rate_limit",
                "too many requests",
            ),
            (
                BadRequestError(
                    "private model detail",
                    response=httpx.Response(
                        400,
                        request=httpx.Request("POST", "https://example.invalid"),
                    ),
                    body={"message": "private model detail"},
                ),
                "model_or_request",
                "GEMINI_MODEL",
            ),
            (
                InternalServerError(
                    "private service detail",
                    response=httpx.Response(
                        503,
                        request=httpx.Request("POST", "https://example.invalid"),
                    ),
                    body={"message": "private service detail"},
                ),
                "api_service",
                "temporarily unavailable",
            ),
        )
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            for error, expected_category, expected_message in cases:
                with self.subTest(category=expected_category):
                    category, _ = _classify_chat_error(error)
                    message = _chat_error_message(error)
                    self.assertEqual(category, expected_category)
                    self.assertIn(expected_message, message)
                    self.assertNotIn("private", message)
                    self.assertNotIn("credential detail", message)

    def test_sanitized_error_diagnostic_does_not_log_api_error_message(self) -> None:
        error = httpx.ReadTimeout("secret key must not appear")
        with self.assertLogs("app.ui.chat.chat_errors", level="ERROR") as captured:
            _log_chat_exception(error)

        output = "\n".join(captured.output)
        self.assertIn("category=timeout", output)
        self.assertIn("status=none", output)
        self.assertNotIn("secret key", output)

    def test_invalid_gemini_timeout_is_not_used(self) -> None:
        from app.agent.agent import DEFAULT_GEMINI_TIMEOUT_SECONDS, gemini_timeout_seconds

        with patch.dict(os.environ, {"GEMINI_TIMEOUT_SECONDS": "not-a-number"}):
            self.assertEqual(gemini_timeout_seconds(), DEFAULT_GEMINI_TIMEOUT_SECONDS)

    def test_greeting_reaches_gemini_with_mcp_tools_available(self) -> None:
        history: list[dict[str, object]] = []
        fake_client = SimpleNamespace()
        fake_genai = SimpleNamespace(aio=_AsyncContext(fake_client))
        agent = AsyncMock(return_value="Gemini-generated greeting")
        stdio_context = _AsyncContext(("read-stream", "write-stream"))
        mcp_session = SimpleNamespace(initialize=AsyncMock())
        session_context = _AsyncContext(mcp_session)
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-key"}),
            patch("app.agent.chat_runtime.respond", agent),
            patch("app.agent.chat_runtime.genai.Client", return_value=fake_genai) as gemini_client,
            patch(
                "app.agent.chat_runtime.stdio_client",
                return_value=stdio_context,
            ) as mcp_client,
            patch(
                "app.agent.chat_runtime.ClientSession",
                return_value=session_context,
            ),
        ):
            answer = asyncio.run(_respond_with_agent("Hii", history))

        self.assertEqual(answer, "Gemini-generated greeting")
        gemini_client.assert_called_once()
        agent.assert_awaited_once()
        self.assertIs(agent.await_args.kwargs["session"], mcp_session)
        mcp_client.assert_called_once()
        mcp_session.initialize.assert_awaited_once()

    def test_product_request_starts_mcp_and_cleans_up_sessions(self) -> None:
        history: list[dict[str, object]] = []
        gemini_context = _AsyncContext(SimpleNamespace())
        stdio_context = _AsyncContext(("read-stream", "write-stream"))
        mcp_session = SimpleNamespace(initialize=AsyncMock())
        session_context = _AsyncContext(mcp_session)
        agent = AsyncMock(return_value="Catalog response")
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-key"}),
            patch(
                "app.agent.chat_runtime.genai.Client",
                return_value=SimpleNamespace(aio=gemini_context),
            ),
            patch(
                "app.agent.chat_runtime.stdio_client",
                return_value=stdio_context,
            ) as mcp_client,
            patch(
                "app.agent.chat_runtime.ClientSession",
                return_value=session_context,
            ) as session_factory,
            patch("app.agent.chat_runtime.respond", agent),
        ):
            answer = asyncio.run(_respond_with_agent("Find a mouse", history))

        self.assertEqual(answer, "Catalog response")
        parameters = mcp_client.call_args.args[0]
        self.assertEqual(parameters.command, sys.executable)
        self.assertEqual(parameters.args, ["-m", "app.mcp.mcp_server"])
        self.assertEqual(parameters.cwd, str(PROJECT_ROOT))
        self.assertEqual(
            session_factory.call_args.args,
            ("read-stream", "write-stream"),
        )
        mcp_session.initialize.assert_awaited_once()
        agent.assert_awaited_once()
        self.assertIs(agent.await_args.kwargs["session"], mcp_session)
        self.assertEqual(
            (gemini_context.enter_count, gemini_context.exit_count),
            (1, 1),
        )
        self.assertEqual(
            (stdio_context.enter_count, stdio_context.exit_count),
            (1, 1),
        )
        self.assertEqual(
            (session_context.enter_count, session_context.exit_count),
            (1, 1),
        )

    def test_mcp_sessions_are_cleaned_up_when_agent_response_fails(self) -> None:
        gemini_context = _AsyncContext(SimpleNamespace())
        stdio_context = _AsyncContext(("read-stream", "write-stream"))
        session_context = _AsyncContext(SimpleNamespace(initialize=AsyncMock()))
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-key"}),
            patch(
                "app.agent.chat_runtime.genai.Client",
                return_value=SimpleNamespace(aio=gemini_context),
            ),
            patch(
                "app.agent.chat_runtime.stdio_client",
                return_value=stdio_context,
            ),
            patch(
                "app.agent.chat_runtime.ClientSession",
                return_value=session_context,
            ),
            patch(
                "app.agent.chat_runtime.respond",
                AsyncMock(side_effect=RuntimeError("agent failure")),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "agent failure"):
                asyncio.run(_respond_with_agent("Find a mouse", []))

        self.assertEqual(
            (gemini_context.enter_count, gemini_context.exit_count),
            (1, 1),
        )
        self.assertEqual(
            (stdio_context.enter_count, stdio_context.exit_count),
            (1, 1),
        )
        self.assertEqual(
            (session_context.enter_count, session_context.exit_count),
            (1, 1),
        )

    def test_displays_catalog_results_without_model_product_claims(self) -> None:
        answer = (
            "A model-generated product claim. "
            "Catalog results from shopping.db:\n"
            "- Real catalog item | ₹500.00 | Rating: 4.5/5"
        )

        grounded = _ground_chat_answer(answer)

        self.assertNotIn("model-generated", grounded)
        self.assertIn("Real catalog item", grounded)
        self.assertIn("₹500.00", grounded)

    def test_preserves_budget_clarification(self) -> None:
        self.assertEqual(
            _ground_chat_answer("What is your maximum budget in rupees?"),
            "What is your maximum budget in rupees?",
        )

    def test_preserves_gemini_greeting_for_greeting_prompt(self) -> None:
        answer = "Hello! How can I help you today?"

        self.assertEqual(_ground_chat_answer(answer, "Hi"), answer)

    def test_preserves_ordinary_gemini_conversation(self) -> None:
        for message, answer in (
            ("How are you?", "I'm doing well. What would you like to know about Shopwise?"),
            ("Thanks", "You're welcome!"),
            ("Who are you?", "I'm Shopwise's shopping assistant."),
        ):
            with self.subTest(message=message):
                self.assertEqual(_ground_chat_answer(answer, message), answer)

    def test_does_not_allow_product_claims_for_non_greeting_without_catalog(self) -> None:
        answer = "Buy the SuperMouse for ₹500."

        grounded = _ground_chat_answer(answer, "Find a mouse")

        self.assertNotIn("SuperMouse", grounded)
        self.assertIn("couldn't verify product matches", grounded)

    def test_rejects_product_claims_without_catalog_results(self) -> None:
        grounded = _ground_chat_answer("Buy the SuperMouse for ₹500.")

        self.assertNotIn("SuperMouse", grounded)
        self.assertIn("couldn't verify product matches", grounded)

    def test_refuses_cover_letter_request(self) -> None:
        answer = (
            "Here is a template you can customize for your applications:\n\n"
            "[Your Name]\n[Your Phone Number]\n\nDear Hiring Manager,"
        )

        grounded = _ground_chat_answer(answer, "i want a cover letter for AI Developer")

        self.assertNotIn("Hiring Manager", grounded)
        self.assertNotIn("[Your Name]", grounded)
        self.assertIn("shopping", grounded.casefold())

    def test_refuses_job_search_request(self) -> None:
        answer = "Here are some tips for landing an AI developer role."

        grounded = _ground_chat_answer(answer, "I am searching for a job as AI developer")

        self.assertNotIn("landing", grounded)
        self.assertIn("shopping", grounded.casefold())

    def test_refuses_philosophical_question(self) -> None:
        answer = "The meaning of life is a wonderfully deep question."

        grounded = _ground_chat_answer(answer, "What is the meaning of life?")

        self.assertNotIn("deep question", grounded)
        self.assertIn("shopping", grounded.casefold())

    def test_refuses_off_topic_answer_without_request_keywords(self) -> None:
        answer = "Dear Hiring Manager,\n\nI am writing to apply for the role."

        grounded = _ground_chat_answer(answer, "Can you help me with something?")

        self.assertNotIn("Hiring Manager", grounded)
        self.assertIn("shopping", grounded.casefold())

    def test_catalog_results_take_priority_over_scope_guard(self) -> None:
        answer = (
            "Catalog results from shopping.db:\n"
            "- Real catalog item | ₹500.00 | Rating: 4.5/5"
        )

        grounded = _ground_chat_answer(answer, "find laptops for my job")

        self.assertIn("Real catalog item", grounded)

    def test_refuses_car_recommendation_request(self) -> None:
        answer = "The best car in India right now is the Tata Nexon."

        grounded = _ground_chat_answer(answer, "can you help me find which is the best car in india")

        self.assertNotIn("Nexon", grounded)
        self.assertIn("shopping", grounded.casefold())
        self.assertIn("cables & chargers", grounded.casefold())

    def test_refusal_names_shopwise_categories(self) -> None:
        grounded = _ground_chat_answer(
            "Sure, here are the best cars.", "best car in india"
        )

        self.assertIn("audio", grounded.casefold())
        self.assertIn("gaming", grounded.casefold())

    def test_refuses_flight_booking_request(self) -> None:
        answer = "You can book cheap flights on any travel portal."

        grounded = _ground_chat_answer(answer, "book a flight to delhi")

        self.assertNotIn("travel portal", grounded)
        self.assertIn("shopping", grounded.casefold())

    def test_strips_generic_assistant_filler_opener(self) -> None:
        answer = (
            "Glad I could help! Let me know if you would like to filter "
            "by a specific category."
        )

        grounded = _ground_chat_answer(answer, "Thanks")

        self.assertNotIn("Glad I could help", grounded)
        self.assertIn("filter", grounded)

    def test_strips_as_an_ai_opener(self) -> None:
        answer = "As an AI, I cannot browse shops. Try the Audio category!"

        grounded = _ground_chat_answer(answer, "How do you work?")

        self.assertNotIn("As an AI", grounded)
        self.assertIn("Audio", grounded)

    def test_filler_only_answer_falls_back_to_verification_message(self) -> None:
        grounded = _ground_chat_answer("Glad I could help!", "Thanks")

        self.assertIn("couldn't verify product matches", grounded)


if __name__ == "__main__":
    unittest.main()
