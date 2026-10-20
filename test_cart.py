import unittest

from app.cart import add_to_cart, cart_total, remove_from_cart, update_cart_quantity


class ShoppingCartTests(unittest.TestCase):
    def setUp(self) -> None:
        self.product = {"id": 7, "price": 125.5, "stock": 4}

    def test_add_increments_quantity_without_mutating_original(self) -> None:
        original = {7: 1}

        updated = add_to_cart(original, self.product)

        self.assertEqual(updated, {7: 2})
        self.assertEqual(original, {7: 1})

    def test_update_quantity_and_recalculate_total(self) -> None:
        cart = add_to_cart({}, self.product, 2)
        cart = update_cart_quantity(cart, self.product, 3)

        self.assertEqual(cart_total(cart, {7: self.product}), 376.5)

    def test_remove_item_and_empty_cart_total(self) -> None:
        cart = remove_from_cart({7: 2, 8: 1}, 7)

        self.assertEqual(cart, {8: 1})
        self.assertEqual(remove_from_cart(cart, 99), cart)
        self.assertEqual(cart_total({}, {}), 0)

    def test_rejects_invalid_quantities_and_stock_overflow(self) -> None:
        for quantity in (0, -1, 1.5, "2", True):
            with self.subTest(quantity=quantity):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    add_to_cart({}, self.product, quantity)

        with self.assertRaisesRegex(ValueError, "available stock"):
            add_to_cart({7: 3}, self.product, 2)
        with self.assertRaisesRegex(ValueError, "available stock"):
            update_cart_quantity({}, self.product, 5)

    def test_rejects_updates_for_missing_items_and_missing_products(self) -> None:
        with self.assertRaisesRegex(ValueError, "not in the cart"):
            update_cart_quantity({}, self.product, 1)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            cart_total({7: 1}, {})


if __name__ == "__main__":
    unittest.main()
