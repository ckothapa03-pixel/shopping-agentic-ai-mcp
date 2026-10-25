import asyncio
import os
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

from app.agent.chat_runtime import _respond_with_agent
from app.ui.chat.chat_errors import (
    _chat_error_message,
    _classify_chat_error,
    _log_chat_exception,
)
from app.ui.chat.chat_grounding import ground_chat_answer as _ground_chat_answer


class _AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
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

    def test_greeting_uses_gemini_without_starting_mcp_server(self) -> None:
        client = SimpleNamespace(
            interactions=SimpleNamespace(
                create=AsyncMock(
                    return_value=SimpleNamespace(
                        steps=[
                            SimpleNamespace(
                                type="model_output",
                                model_dump=lambda **_kwargs: {
                                    "type": "model_output",
                                    "content": [],
                                },
                            )
                        ],
                        output_text="Hello! What can I help you find today?",
                    )
                )
            )
        )
        gemini_client = SimpleNamespace(aio=_AsyncContext(client))
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-key"}),
            patch("app.agent.chat_runtime.load_dotenv"),
            patch(
                "app.agent.chat_runtime.genai.Client",
                return_value=gemini_client,
            ) as gemini_client_factory,
            patch("app.agent.chat_runtime.stdio_client", new_callable=AsyncMock) as mcp_client,
        ):
            answer = asyncio.run(_respond_with_agent("Hii", []))

        self.assertIn("Hello!", answer)
        client.interactions.create.assert_awaited_once()
        retry_options = gemini_client_factory.call_args.kwargs[
            "http_options"
        ].retry_options
        self.assertEqual(retry_options.attempts, 2)
        self.assertNotIn(429, retry_options.http_status_codes)
        mcp_client.assert_not_awaited()

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


if __name__ == "__main__":
    unittest.main()
