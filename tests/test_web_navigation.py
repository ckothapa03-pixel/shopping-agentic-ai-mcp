import asyncio
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from google.genai.errors import ClientError
from app.db.products import count_products, find_products, get_catalog_facets
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parent.parent / "app" / "ui" / "web_app.py"
PROJECT_ROOT = APP_PATH.parents[2]
ACCOUNTS_SCHEMA_PATH = PROJECT_ROOT / "scripts" / "accounts_schema.sql"


class _AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return None


class ShoppingAccessNavigationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_auth_database = os.environ.get("SHOPPING_AUTH_DB")
        file_descriptor, database_path = tempfile.mkstemp(
            prefix="accounts-navigation-test-", suffix=".sqlite3", dir=PROJECT_ROOT
        )
        os.close(file_descriptor)
        self.database_path = Path(database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.executescript(ACCOUNTS_SCHEMA_PATH.read_text(encoding="utf-8"))
        os.environ["SHOPPING_AUTH_DB"] = str(self.database_path)
        self.app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()

    def tearDown(self) -> None:
        if self.previous_auth_database is None:
            os.environ.pop("SHOPPING_AUTH_DB", None)
        else:
            os.environ["SHOPPING_AUTH_DB"] = self.previous_auth_database
        self.database_path.unlink(missing_ok=True)

    def _button(self, label: str):
        return next(button for button in self.app.button if button.label == label)

    def _text_input(self, key: str):
        return next(widget for widget in self.app.text_input if widget.key == key)

    def _submit(self, label: str):
        return next(
            button
            for button in self.app.form_submit_button
            if button.label == label
        )

    def _assert_no_shop(self) -> None:
        self.assertNotIn(
            "Shop the catalog",
            [header.value for header in self.app.header],
        )

    def test_login_screen_is_the_initial_view_and_protects_the_shop(self) -> None:
        self.assertFalse(self.app.exception)
        self.assertEqual(
            [widget.key for widget in self.app.text_input],
            ["login-email", "login-password"],
        )
        self.assertIn(
            "Login",
            [button.label for button in self.app.form_submit_button],
        )
        self._assert_no_shop()

    def test_guest_navigation_opens_shop_and_return_reopens_login(self) -> None:
        self._button("Continue as Guest").click().run()
        self.assertEqual(
            self.app.menu_button(key="account-menu").options,
            ["Login"],
        )

        self.assertTrue(any(item.value == "Shop by Category" for item in self.app.subheader))
        self._button("View all products").click().run()
        self.assertIn("Shop all products", [item.value for item in self.app.header])
        self.assertTrue(self.app.subheader)
        add_button = next(
            button for button in self.app.button if button.label == "Add to cart"
        )
        add_button.click().run()
        self.assertEqual(len(self.app.session_state["cart"]), 1)
        self.assertTrue(any(button.key == "open-cart" for button in self.app.button))
        self.assertTrue(
            any("Cart total:" in element.value for element in self.app.markdown)
        )
        self.assertEqual(
            self.app.menu_button(key="account-menu").options,
            ["Login"],
        )
        self.app.menu_button(key="account-menu").click("Login").run()

        self._assert_no_shop()
        self.assertEqual(
            [widget.key for widget in self.app.text_input],
            ["login-email", "login-password"],
        )

    def test_invalid_credentials_do_not_open_the_shop(self) -> None:
        self._text_input("login-email").set_value("unknown@example.com")
        self._text_input("login-password").set_value("incorrect-password")
        self._submit("Login").click().run()

        self.assertIn(
            "Invalid email or password.",
            [error.value for error in self.app.error],
        )
        self._assert_no_shop()

    def test_create_account_then_verified_login_opens_authenticated_shop(self) -> None:
        self._button("Create an account").click().run()
        self.assertIn(
            "Create your account",
            [header.value for header in self.app.subheader],
        )
        self._assert_no_shop()

        self._text_input("register-name").set_value("Demo Shopper")
        self._text_input("register-email").set_value("demo@example.com")
        self._text_input("register-password").set_value("demo-password")
        self._text_input("register-confirm-password").set_value("demo-password")
        self._submit("Create account").click().run()
        self.assertIn(
            "Account created. Sign in with your new credentials.",
            [element.value for element in self.app.success],
        )
        self._assert_no_shop()

        self._text_input("login-email").set_value("demo@example.com")
        self._text_input("login-password").set_value("wrong-password")
        self._submit("Login").click().run()
        self.assertIn(
            "Invalid email or password.",
            [error.value for error in self.app.error],
        )
        self._assert_no_shop()

        self._text_input("login-email").set_value("demo@example.com")
        self._text_input("login-password").set_value("demo-password")
        self._submit("Login").click().run()

        self.assertTrue(
            any(item.value == "Shop by Category" for item in self.app.subheader)
        )
        self.assertTrue(
            any("Welcome, Demo Shopper" in item.value for item in self.app.caption)
        )
        self.assertEqual(
            self.app.menu_button(key="account-menu").options,
            ["Profile", "Settings", "Logout"],
        )
        self.app.menu_button(key="account-menu").click("Profile").run()
        self.assertIn("Your profile", [header.value for header in self.app.header])
        self.assertTrue(
            any("demo@example.com" in element.value for element in self.app.markdown)
        )
        self.app.menu_button(key="account-menu").click("Settings").run()
        self.assertIn("Settings", [header.value for header in self.app.header])
        layout_radio = next(
            radio
            for radio in self.app.radio
            if radio.label == "Default catalog layout"
        )
        layout_radio.set_value("List")
        self._button("Save settings").click().run()
        self.assertEqual(self.app.session_state["catalog_layout_preference"], "List")
        next(button for button in self.app.button if button.label == "Add to cart").click().run()
        next(button for button in self.app.button if button.label == "Save").click().run()
        chat_history = [{"role": "user", "content": "Keep chat after logout."}]
        self.app.session_state["chat_messages"] = chat_history.copy()
        self.app.menu_button(key="account-menu").click("Logout").run()
        self.assertEqual(self.app.session_state["access_mode"], "guest")
        self.assertEqual(
            self.app.menu_button(key="account-menu").options,
            ["Login"],
        )
        self.assertNotIn("authenticated_email", self.app.session_state)
        self.assertNotIn("authenticated_name", self.app.session_state)
        self.assertEqual(len(self.app.session_state["cart"]), 1)
        self.assertEqual(len(self.app.session_state["wishlist"]), 1)
        self.assertEqual(self.app.session_state["chat_messages"], chat_history)

    def test_logo_returns_to_home_and_preserves_shopping_and_chat_state(self) -> None:
        self._button("Continue as Guest").click().run()
        next(button for button in self.app.button if button.label == "Add to cart").click().run()
        next(button for button in self.app.button if button.label == "Save").click().run()
        chat_history = [{"role": "user", "content": "Keep this conversation."}]
        self.app.session_state["chat_messages"] = chat_history.copy()

        self.app.button(key="home-category-select-0").click().run()
        self.assertTrue(self.app.session_state["catalog_view"])
        self.app.button(key="home-logo").click().run()

        self.assertFalse(self.app.session_state["catalog_view"])
        self.assertEqual(self.app.session_state["catalog_page"], 1)
        self.assertTrue(any(item.value == "Shop by Category" for item in self.app.subheader))
        self.assertTrue(any(item.value == "Featured Products" for item in self.app.subheader))
        self.assertEqual(len(self.app.session_state["cart"]), 1)
        self.assertEqual(len(self.app.session_state["wishlist"]), 1)
        self.assertEqual(self.app.session_state["chat_messages"], chat_history)

        self._text_input("catalog_search_input").set_value("router")
        self._submit("Search").click().run()
        self.assertTrue(self.app.session_state["catalog_view"])
        self.app.button(key="home-logo").click().run()
        self.assertFalse(self.app.session_state["catalog_view"])
        self.assertEqual(self.app.session_state["catalog_search_query"], "")
        self.assertEqual(len(self.app.session_state["cart"]), 1)
        self.assertEqual(len(self.app.session_state["wishlist"]), 1)
        self.assertEqual(self.app.session_state["chat_messages"], chat_history)

        self._button("View all products").click().run()
        self.assertTrue(self.app.session_state["catalog_view"])
        self.app.button(key="home-logo").click().run()
        self.assertFalse(self.app.session_state["catalog_view"])
        self.assertTrue(any(item.value == "Shop by Category" for item in self.app.subheader))
        self.assertEqual(len(self.app.session_state["cart"]), 1)
        self.assertEqual(len(self.app.session_state["wishlist"]), 1)
        self.assertEqual(self.app.session_state["chat_messages"], chat_history)

    def test_wishlist_updates_and_is_session_only(self) -> None:
        self._button("Continue as Guest").click().run()

        next(
            button for button in self.app.button if button.label == "Save"
        ).click().run()

        self.assertEqual(len(self.app.session_state["wishlist"]), 1)
        self.app.button(key="open-wishlist").click().run()

        self.assertIn(
            "Your wishlist",
            [header.value for header in self.app.header],
        )
        self.assertTrue(
            any(
                "temporary and stored only in this browser session" in element.value
                for element in self.app.info
            )
        )
        next(
            button
            for button in self.app.button
            if button.key and button.key.startswith("wishlist-product-")
        ).click().run()
        self.assertFalse(self.app.session_state["wishlist"])

    def test_demo_checkout_rechecks_cart_without_persisting_an_order(self) -> None:
        self._button("Continue as Guest").click().run()
        next(
            button for button in self.app.button if button.label == "Add to cart"
        ).click().run()
        self.app.button(key="open-cart").click().run()
        next(
            button for button in self.app.button if button.label == "Checkout"
        ).click().run()

        self.assertIn(
            "Demo checkout",
            [header.value for header in self.app.header],
        )
        self.assertTrue(
            any("no order is saved" in element.value for element in self.app.warning)
        )
        next(
            button
            for button in self.app.button
            if button.label == "Complete demo checkout"
        ).click().run()

        self.assertTrue(
            any(
                "No order was placed or stored" in element.value
                for element in self.app.success
            )
        )
        self.assertEqual(len(self.app.session_state["cart"]), 1)

    def test_header_search_and_clear_filters_restore_the_catalog(self) -> None:
        self._button("Continue as Guest").click().run()
        self._text_input("catalog_search_input").set_value(
            "__no_shopwise_match__"
        )
        self._submit("Search").click().run()

        self.assertTrue(
            any("No products match" in element.value for element in self.app.info)
        )
        self._button("Clear all filters").click().run()

        self.assertEqual(self.app.session_state["catalog_search_query"], "")
        self.assertFalse(
            any("No products match" in element.value for element in self.app.info)
        )

    def test_clearing_only_search_returns_to_home_without_stale_results(self) -> None:
        self._button("Continue as Guest").click().run()
        self._text_input("catalog_search_input").set_value("__no_shopwise_match__")
        self._submit("Search").click().run()
        self.assertTrue(self.app.session_state["catalog_view"])

        self._button("Clear search").click().run()

        self.assertEqual(self.app.session_state["catalog_search_query"], "")
        self.assertEqual(self.app.session_state["catalog_page"], 1)
        self.assertFalse(self.app.session_state["catalog_view"])
        self.assertTrue(
            any(item.value == "Shop by Category" for item in self.app.subheader)
        )
        self.assertFalse(
            any("No products match" in item.value for item in self.app.info)
        )

    def test_homepage_categories_use_real_catalog_values(self) -> None:
        self._button("Continue as Guest").click().run()

        categories = get_catalog_facets()["categories"]
        category_buttons = [
            button for button in self.app.button
            if button.key.startswith("home-category-select-")
        ]
        self.assertEqual(len(categories), 10)
        self.assertEqual([button.label for button in category_buttons], categories)
        self.assertFalse(any("category-nav-" in button.key for button in self.app.button))
        self.assertTrue(
            any("Discover a Smarter Way to Shop" in item.value for item in self.app.markdown)
        )
        self.assertTrue(any(item.value == "Shop by Category" for item in self.app.subheader))
        self.assertFalse(
            any(f"{count_products()} products" in item.value for item in self.app.markdown)
        )
        self.assertFalse(any(button.key.startswith("catalog-bottom-") for button in self.app.button))

        expected_featured = find_products(sort_by="highest_rated", limit=6)
        featured_ids = {
            int(button.key.removeprefix("add-product-"))
            for button in self.app.button
            if button.key.startswith("add-product-")
        }
        self.assertEqual(featured_ids, {product["id"] for product in expected_featured})

        self.app.button(key="home-category-select-0").click().run()
        self.assertEqual(self.app.session_state["category_select"], categories[0])
        self.assertIn(categories[0], [item.value for item in self.app.header])
        self.assertTrue(any("products" in item.value for item in self.app.markdown))
        category_product_ids = {
            int(button.key.removeprefix("add-product-"))
            for button in self.app.button
            if button.key.startswith("add-product-")
        }
        self.assertEqual(
            category_product_ids,
            {product["id"] for product in find_products(category=categories[0], limit=15)},
        )

    def test_view_all_products_opens_full_results_with_pagination_below_grid(self) -> None:
        self._button("Continue as Guest").click().run()
        self._button("View all products").click().run()

        self.assertIn("Shop all products", [item.value for item in self.app.header])
        self.assertTrue(
            any(f"{count_products()} products" in item.value for item in self.app.markdown)
        )
        product_buttons = [
            button for button in self.app.button
            if button.key.startswith("add-product-")
        ]
        self.assertEqual(len(product_buttons), 15)
        next_button = next(button for button in self.app.button if button.label == "Next")
        button_positions = {button.key: index for index, button in enumerate(self.app.button)}
        self.assertGreater(
            button_positions[next_button.key],
            max(button_positions[button.key] for button in product_buttons),
        )

    def test_shop_now_opens_the_full_catalog(self) -> None:
        self._button("Continue as Guest").click().run()
        self._button("Shop now").click().run()

        self.assertIn("Shop all products", [item.value for item in self.app.header])
        self.assertTrue(
            any(f"{count_products()} products" in item.value for item in self.app.markdown)
        )

    def test_pagination_and_clear_search_preserve_catalog_filters(self) -> None:
        self._button("Continue as Guest").click().run()
        self._button("View all products").click().run()
        next_button = next(button for button in self.app.button if button.label == "Next")
        next_button.click().run()
        self.assertEqual(self.app.session_state["catalog_page"], 2)
        self.assertTrue(any("Page 2 of" in item.value for item in self.app.caption))

        category = self.app.selectbox(key="category_select")
        selected_category = category.options[1]
        category.select(selected_category).run()
        self.assertEqual(self.app.session_state["catalog_page"], 1)

        self._text_input("catalog_search_input").set_value("__no_shopwise_match__")
        self._submit("Search").click().run()
        self.assertEqual(self.app.session_state["catalog_page"], 1)
        self._button("Clear search").click().run()
        self.assertEqual(self.app.session_state["catalog_search_query"], "")
        self.assertEqual(self.app.session_state["category_select"], selected_category)

    def test_chat_history_renders_user_and_assistant_messages_in_history(self) -> None:
        self._button("Continue as Guest").click().run()
        product = find_products(limit=1)[0]
        self.app.session_state["chat_messages"] = [
            {"role": "user", "content": "Find a mouse under ₹1,000."},
            {
                "role": "assistant",
                "content": (
                    "Here is a matching product from the Shopwise catalog."
                ),
                "products": [product],
            },
        ]
        self.app.button(key="open-chat").click().run()

        rendered_markdown = [element.value for element in self.app.markdown]
        self.assertTrue(
            any("Find a mouse under ₹1,000." in value for value in rendered_markdown)
        )
        self.assertTrue(
            any(product["name"] in value for value in rendered_markdown)
        )
        self.assertTrue(
            any("Product image unavailable" in value for value in rendered_markdown)
        )
        self.assertTrue(
            any(f"₹{product['price']:,.2f}" in value for value in rendered_markdown)
        )
        popup = self.app.get_by_key("chat-popup")
        rendered_chat_messages = popup.chat_message
        self.assertEqual(
            [message.name for message in rendered_chat_messages],
            ["user", "assistant"],
        )
        self.assertEqual(
            [message.avatar for message in rendered_chat_messages],
            [":material/person:", ":material/smart_toy:"],
        )
        self.assertTrue(self.app.get_by_key("chat-message-list").proto.autoscroll)

        style_source = (PROJECT_ROOT / "assets" / "css" / "store.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(":has([data-testid=\"chatAvatarIcon-user\"])", style_source)
        self.assertIn("overflow-wrap: anywhere", style_source)
        self.assertIn("white-space: nowrap", style_source)
        self.assertIn('[data-testid="InputInstructions"]', style_source)
        self.assertFalse(self.app.exception)

    def test_chat_popup_opens_and_closes_without_losing_conversation(self) -> None:
        self._button("Continue as Guest").click().run()
        history = [{"role": "user", "content": "Please keep this message."}]
        self.app.session_state["chat_messages"] = history.copy()
        self.assertTrue(any(button.key == "open-chat" for button in self.app.button))

        self.app.button(key="open-chat").click().run()

        self.assertTrue(self.app.session_state["chat_open"])
        self.assertTrue(any(button.key == "close-chat" for button in self.app.button))
        self.assertTrue(
            any("Please keep this message." in item.value for item in self.app.markdown)
        )

        self.app.button(key="close-chat").click().run()

        self.assertFalse(self.app.session_state["chat_open"])
        self.assertTrue(any(button.key == "open-chat" for button in self.app.button))
        self.assertEqual(self.app.session_state["chat_messages"], history)
        self.assertFalse(self.app.exception)

    def test_submitted_greeting_is_saved_rendered_once_across_rerun(self) -> None:
        self._button("Continue as Guest").click().run()
        self.app.button(key="open-chat").click().run()
        popup = self.app.get_by_key("chat-popup")
        chat_form = next(
            form for form in popup.form if form.key == "shopwise-chat-form"
        )
        self.assertTrue(chat_form.proto.form.enter_to_submit)
        self.assertEqual(
            [widget.key for widget in chat_form.text_input], ["chat-prompt"]
        )
        self.assertEqual(
            [button.label for button in chat_form.form_submit_button], ["Send"]
        )
        response = "Hello! What can I help you find today?"
        agent = AsyncMock(return_value=response)
        fake_genai = SimpleNamespace(aio=_AsyncContext(SimpleNamespace()))

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-key"}),
            patch("app.agent.chat_runtime.respond", agent),
            patch("google.genai.Client", return_value=fake_genai),
        ):
            next(
                widget
                for widget in self.app.text_input
                if widget.label == "Message the shopping assistant"
            ).set_value("Hii")
            next(
                button
                for button in self.app.form_submit_button
                if button.label == "Send"
            ).click().run()

        self.assertEqual(
            self.app.session_state["chat_messages"],
            [
                {"role": "user", "content": "Hii"},
                {"role": "assistant", "content": response, "products": []},
            ],
        )
        rendered = [item.value for item in self.app.markdown]
        self.assertTrue(any("Hii" in value for value in rendered))
        self.assertTrue(any(response in value for value in rendered))
        self.assertIsNone(self.app.session_state["chat_pending_reply"])
        self.assertFalse(self.app.session_state["chat_processing"])
        self.assertNotIn("pending", self.app.session_state["chat_messages"][1])
        self.assertEqual(self._text_input("chat-prompt").value, "")
        self.assertFalse(self._text_input("chat-prompt").disabled)
        self.assertFalse(self._submit("Send").disabled)
        agent.assert_awaited_once()

        self.app.run()
        self.assertEqual(len(self.app.session_state["chat_messages"]), 2)
        agent.assert_awaited_once()

    def test_three_consecutive_messages_receive_replies_in_the_same_submission(self) -> None:
        self._button("Continue as Guest").click().run()
        self.app.button(key="open-chat").click().run()
        messages_and_replies = [
            ("Hello", "Reply to Hello"),
            ("Hii", "Reply to Hii"),
            ("Hello", "Second reply to Hello"),
        ]
        replies = iter(reply for _, reply in messages_and_replies)

        async def stream_reply(*_args, **kwargs):
            submitted_prompt = kwargs["user_message"]
            in_flight_history = self.app.session_state["chat_messages"]
            self.assertTrue(self.app.session_state["chat_processing"])
            self.assertEqual(in_flight_history[-2]["content"], submitted_prompt)
            self.assertTrue(in_flight_history[-1]["pending"])
            reply = next(replies)
            on_text_delta = kwargs.get("on_text_delta")
            if on_text_delta is not None:
                on_text_delta(reply[:5])
                on_text_delta(reply[5:])
            return reply

        agent = AsyncMock(side_effect=stream_reply)
        fake_genai = SimpleNamespace(aio=_AsyncContext(SimpleNamespace()))

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-key"}),
            patch("app.agent.chat_runtime.respond", agent),
            patch("google.genai.Client", return_value=fake_genai),
        ):
            for index, (prompt, reply) in enumerate(messages_and_replies, start=1):
                # Model the form callback's real handoff: it captures the
                # typed value, clears the widget, then Streamlit reruns. In
                # that rerun the button value may be false, so the queued
                # value must be the authoritative submission signal.
                input_widget = self._text_input("chat-prompt")
                input_widget.set_value(prompt)
                self.app.session_state["chat-submitted-prompt"] = prompt
                input_widget.set_value("")
                self.app.run()

                history = self.app.session_state["chat_messages"]
                self.assertEqual(len(history), index * 2)
                self.assertEqual(history[-2]["role"], "user")
                self.assertEqual(history[-2]["content"], prompt)
                self.assertEqual(history[-1]["role"], "assistant")
                self.assertEqual(history[-1]["content"], reply)
                self.assertTrue(self.app.session_state["chat_open"])
                self.assertNotIn("pending", history[-1])
                self.assertIsNone(self.app.session_state["chat_pending_reply"])
                self.assertEqual(self._text_input("chat-prompt").value, "")
                rendered = [item.value for item in self.app.markdown]
                self.assertTrue(
                    any(prompt in value for value in rendered),
                    f"User message {prompt!r} was not rendered during its submission",
                )
                self.assertTrue(
                    any(reply in value for value in rendered),
                    f"Reply for {prompt!r} was not rendered during its submission",
                )
                for previous_prompt, previous_reply in messages_and_replies[:index - 1]:
                    self.assertTrue(
                        any(previous_prompt in value for value in rendered),
                        f"Earlier user message {previous_prompt!r} disappeared",
                    )
                    self.assertTrue(
                        any(previous_reply in value for value in rendered),
                        f"Earlier assistant reply {previous_reply!r} disappeared",
                    )
                self.assertEqual(agent.await_count, index)

        final_history = self.app.session_state["chat_messages"]
        for prompt, reply in messages_and_replies:
            expected_prompt_count = sum(
                submitted_prompt == prompt
                for submitted_prompt, _ in messages_and_replies
            )
            self.assertEqual(
                sum(
                    message["role"] == "user" and message["content"] == prompt
                    for message in final_history
                ),
                expected_prompt_count,
            )
            self.assertEqual(
                sum(
                    message["role"] == "assistant" and message["content"] == reply
                    for message in final_history
                ),
                1,
            )
        self.assertEqual(agent.await_count, 3)

    def test_chat_failure_is_saved_as_a_visible_friendly_reply(self) -> None:
        self._button("Continue as Guest").click().run()
        self.app.button(key="open-chat").click().run()
        agent = AsyncMock(side_effect=TimeoutError("private timeout detail"))
        fake_genai = SimpleNamespace(aio=_AsyncContext(SimpleNamespace()))

        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-key"}),
            patch("app.agent.chat_runtime.respond", agent),
            patch("google.genai.Client", return_value=fake_genai),
        ):
            next(
                widget
                for widget in self.app.text_input
                if widget.label == "Message the shopping assistant"
            ).set_value("Hello")
            next(
                button
                for button in self.app.form_submit_button
                if button.label == "Send"
            ).click().run()

        self.assertEqual(len(self.app.session_state["chat_messages"]), 2)
        self.assertEqual(self.app.session_state["chat_messages"][0]["content"], "Hello")
        error_reply = self.app.session_state["chat_messages"][1]["content"]
        self.assertIn("timed out", error_reply)
        self.assertNotIn("private timeout detail", error_reply)
        self.assertTrue(any(error_reply in item.value for item in self.app.markdown))
        self.assertTrue(self.app.session_state["chat_open"])
        self.assertIsNone(self.app.session_state["chat_pending_reply"])
        self.assertFalse(self.app.session_state["chat_processing"])
        self.assertNotIn("pending", self.app.session_state["chat_messages"][1])
        self.assertEqual(self._text_input("chat-prompt").value, "")
        self.assertFalse(self._text_input("chat-prompt").disabled)
        self.assertFalse(self._submit("Send").disabled)
        agent.assert_awaited_once()

    def test_slow_greeting_completes_and_clears_processing_state(self) -> None:
        self._button("Continue as Guest").click().run()
        self.app.button(key="open-chat").click().run()

        async def slow_reply(*_args, **_kwargs):
            await asyncio.sleep(0.02)
            return "Hello! I'm ready to help."

        agent = AsyncMock(side_effect=slow_reply)
        fake_genai = SimpleNamespace(aio=_AsyncContext(SimpleNamespace()))
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-key"}),
            patch("app.agent.chat_runtime.respond", agent),
            patch("google.genai.Client", return_value=fake_genai),
        ):
            self._text_input("chat-prompt").set_value("Hello")
            self._submit("Send").click().run()

        history = self.app.session_state["chat_messages"]
        self.assertEqual([item["role"] for item in history], ["user", "assistant"])
        self.assertEqual(history[1]["content"], "Hello! I'm ready to help.")
        rendered = [item.value for item in self.app.markdown]
        self.assertTrue(any("Hello" in value for value in rendered))
        self.assertTrue(any(history[1]["content"] in value for value in rendered))
        self.assertFalse(self.app.session_state["chat_processing"])
        self.assertIsNone(self.app.session_state["chat_pending_reply"])
        self.assertFalse(self._text_input("chat-prompt").disabled)
        agent.assert_awaited_once()

    def test_api_failure_is_visible_and_the_next_greeting_succeeds(self) -> None:
        self._button("Continue as Guest").click().run()
        self.app.button(key="open-chat").click().run()
        agent = AsyncMock(
            side_effect=[
                ClientError(429, {"message": "private quota detail"}),
                "Hello again!",
            ]
        )
        fake_genai = SimpleNamespace(aio=_AsyncContext(SimpleNamespace()))
        with (
            patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-key"}),
            patch("app.agent.chat_runtime.respond", agent),
            patch("google.genai.Client", return_value=fake_genai),
        ):
            self._text_input("chat-prompt").set_value("Hello")
            self._submit("Send").click().run()

            self.assertIn(
                "too many requests",
                self.app.session_state["chat_messages"][1]["content"],
            )
            self.assertFalse(self.app.session_state["chat_processing"])
            self.assertFalse(self._text_input("chat-prompt").disabled)

            self._text_input("chat-prompt").set_value("Hii")
            self._submit("Send").click().run()

        history = self.app.session_state["chat_messages"]
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0]["content"], "Hello")
        self.assertIn("too many requests", history[1]["content"])
        self.assertNotIn("private quota detail", history[1]["content"])
        self.assertEqual(history[2]["content"], "Hii")
        self.assertEqual(history[3]["content"], "Hello again!")
        self.assertFalse(self.app.session_state["chat_processing"])
        self.assertIsNone(self.app.session_state["chat_pending_reply"])
        self.assertEqual(agent.await_count, 2)

    def test_interrupted_submission_recovers_with_a_visible_reply(self) -> None:
        self._button("Continue as Guest").click().run()
        self.app.session_state["chat_messages"] = [
            {"role": "user", "content": "Hey"},
            {
                "role": "assistant",
                "content": "I'm preparing a reply…",
                "pending": True,
            },
        ]
        self.app.session_state["chat_pending_reply"] = {
            "assistant_index": 1,
            "user_message": "Hey",
        }
        self.app.button(key="open-chat").click().run()

        messages = self.app.session_state["chat_messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["content"], "Hey")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertIn("couldn't complete that reply", messages[1]["content"])
        self.assertNotIn("pending", messages[1])
        self.assertIsNone(self.app.session_state["chat_pending_reply"])
        self.assertTrue(
            any(messages[1]["content"] in item.value for item in self.app.markdown)
        )


if __name__ == "__main__":
    unittest.main()
