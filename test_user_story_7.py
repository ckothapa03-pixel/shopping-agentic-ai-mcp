import unittest

from app.db.products import find_products
from app.tools.products_tool import search_products


class ProductBudgetSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.products = find_products(limit=1000)
        if not cls.products:
            raise AssertionError("The existing product database has no products")

    def test_products_are_within_budget_and_more_expensive_products_are_excluded(
        self,
    ) -> None:
        cheapest = min(self.products, key=lambda product: product["price"])
        more_expensive = [
            product
            for product in self.products
            if product["price"] > cheapest["price"]
        ]

        results = search_products(max_price=cheapest["price"], limit=1000)

        self.assertTrue(results)
        self.assertTrue(
            all(product["price"] <= cheapest["price"] for product in results)
        )
        self.assertTrue(more_expensive)
        result_ids = {product["id"] for product in results}
        self.assertNotIn(more_expensive[0]["id"], result_ids)

    def test_keyword_search_matches_existing_product_name(self) -> None:
        product = self.products[0]
        keyword = product["name"].split()[0]

        results = search_products(search_term=keyword, limit=1000)

        self.assertTrue(
            any(product["id"] == self.products[0]["id"] for product in results)
        )

    def test_budget_rating_and_stock_filters_apply_together(self) -> None:
        in_stock = [
            product for product in self.products if product["stock"] > 0
        ]
        self.assertTrue(in_stock, "The product database has no in-stock products")
        target = max(in_stock, key=lambda product: product["rating_avg"])

        results = search_products(
            search_term=target["sku"],
            max_price=target["price"],
            min_rating=target["rating_avg"],
            in_stock=True,
            limit=1000,
        )

        self.assertEqual([product["id"] for product in results], [target["id"]])
        self.assertTrue(
            all(
                product["price"] <= target["price"]
                and product["rating_avg"] >= target["rating_avg"]
                and product["stock"] > 0
                for product in results
            )
        )

    def test_no_match_returns_empty_list(self) -> None:
        self.assertEqual(
            search_products(search_term="__no_matching_product_story_7__"),
            [],
        )

    def test_limit_is_respected_and_invalid_limits_are_rejected(self) -> None:
        self.assertLessEqual(len(search_products(limit=1)), 1)

        for invalid_limit in (0, -1, 1.5, "5", True):
            with self.subTest(limit=invalid_limit):
                with self.assertRaisesRegex(
                    ValueError, "limit must be a positive integer"
                ):
                    search_products(limit=invalid_limit)

    def test_product_details_are_returned(self) -> None:
        product = search_products(limit=1)[0]

        for field in (
            "name",
            "price",
            "rating_avg",
            "stock",
            "brand",
            "category",
        ):
            with self.subTest(field=field):
                self.assertIn(field, product)


if __name__ == "__main__":
    unittest.main()
