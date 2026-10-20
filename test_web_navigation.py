import os
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parent / "app" / "web_app.py"


class ShoppingAccessNavigationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.previous_auth_database = os.environ.get("SHOPPING_AUTH_DB")
        os.environ["SHOPPING_AUTH_DB"] = str(
            Path(self.temporary_directory.name) / "accounts.sqlite3"
        )
        self.app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()

    def tearDown(self) -> None:
        if self.previous_auth_database is None:
            os.environ.pop("SHOPPING_AUTH_DB", None)
        else:
            os.environ["SHOPPING_AUTH_DB"] = self.previous_auth_database
        self.temporary_directory.cleanup()

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

        self.assertIn(
            "Shop the catalog",
            [header.value for header in self.app.header],
        )
        self.assertTrue(self.app.subheader)
        add_button = next(
            button for button in self.app.button if button.label == "Add to cart"
        )
        add_button.click().run()
        self.assertEqual(len(self.app.session_state["cart"]), 1)
        self.assertTrue(
            any("Cart total:" in element.value for element in self.app.markdown)
        )
        self._button("Return to login").click().run()

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

        self.assertIn(
            "Shop the catalog",
            [header.value for header in self.app.header],
        )
        self.assertIn(
            "Welcome, Demo Shopper",
            [header.value for header in self.app.subheader],
        )
        self._button("Log out").click().run()
        self._assert_no_shop()


if __name__ == "__main__":
    unittest.main()
