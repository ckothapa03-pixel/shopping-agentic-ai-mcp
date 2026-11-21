from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import app.db.database as database
from app.db.products import find_products, get_products_by_ids
from app.shopping.money import money
from tests.database_fixture import create_shopwise_databases


APP_PATH = Path(__file__).resolve().parents[1] / "app" / "ui" / "web_app.py"


class CheckoutConfirmationUiTests(unittest.TestCase):
    def setUp(self) -> None:
        original_db_path = database.DB_PATH
        self.addCleanup(setattr, database, "DB_PATH", original_db_path)
        self.shopping_db, self.account_db = create_shopwise_databases(self)
        database.DB_PATH = self.shopping_db
        schema_path = patch("app.db.schema.DB_PATH", self.shopping_db)
        schema_path.start()
        self.addCleanup(schema_path.stop)
        auth_path = patch.dict(
            "os.environ", {"SHOPPING_AUTH_DB": str(self.account_db)}
        )
        auth_path.start()
        self.addCleanup(auth_path.stop)

    def test_changed_checkout_parameters_invalidate_review_before_confirmation(self) -> None:
        product = get_products_by_ids([find_products(limit=1)[0]["id"]])[0]
        user_id = "USR-CONFIRMATION-TEST"
        address = {
            "id": 7,
            "label": "Home",
            "line1": "1 Test Road",
            "city": "Test City",
            "state": "Test State",
            "pincode": "123456",
            "is_default": True,
        }
        persisted_cart = [
            {"product_id": product["id"], "quantity": 1, "product": product}
        ]
        app = AppTest.from_file(str(APP_PATH), default_timeout=30)

        with (
            patch(
                "app.ui.auth.authenticate_account",
                return_value={
                    "email": "shopper@example.com",
                    "full_name": "Test Shopper",
                    "user_id": user_id,
                },
            ),
            patch("app.ui.web_app.get_cart", return_value=[]),
            patch("app.ui.web_app.set_cart_quantity"),
            patch("app.ui.checkout_page.list_addresses", return_value=[address]),
            patch("app.ui.checkout_page.get_cart", return_value=persisted_cart),
            patch(
                "app.ui.checkout_page.calculate_coupon_discount",
                return_value=Decimal("0"),
            ),
            patch(
                "app.ui.checkout_page.create_order",
                return_value={"order_id": 52},
            ) as create_order,
        ):
            app.run()
            app.text_input(key="login-email").set_value("shopper@example.com")
            app.text_input(key="login-password").set_value("test-password")
            app.form_submit_button(key="login-submit").click().run()
            app.session_state["cart"] = {product["id"]: 1}
            app.session_state["store_page"] = "checkout"
            app.run()

            next(button for button in app.button if button.label == "Review and place order").click().run()
            self.assertIn("pending_checkout_confirmation", app.session_state)

            next(widget for widget in app.text_input if widget.label == "Coupon code").set_value("SAVE10").run()
            self.assertNotIn("pending_checkout_confirmation", app.session_state)
            self.assertTrue(any(button.label == "Review and place order" for button in app.button))

            next(button for button in app.button if button.label == "Review and place order").click().run()
            confirm = next(button for button in app.button if button.label.startswith("Confirm order · ₹"))
            self.assertIn(f"{product['price']:,.2f}", confirm.label)
            confirm.click().run()

        create_order.assert_called_once()
        self.assertEqual(create_order.call_args.args[:4], (user_id, address["id"], "COD", "SAVE10"))
        self.assertEqual(
            create_order.call_args.kwargs["expected_cart"],
            [(product["id"], 1, str(money(product["price"])))],
        )
        self.assertEqual(
            create_order.call_args.kwargs["expected_total"],
            money(product["price"]),
        )


if __name__ == "__main__":
    unittest.main()
