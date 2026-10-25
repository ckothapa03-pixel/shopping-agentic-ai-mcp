import unittest

from app.db.products import (
    count_products,
    find_products,
    get_catalog_facets,
    get_products_by_ids,
)


class ProductCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = find_products(limit=1000)
        if not cls.catalog:
            raise AssertionError("The existing product catalog is empty")

    def test_search_returns_matching_catalog_products(self) -> None:
        product = self.catalog[0]

        results = find_products(search_term=product["sku"], limit=1000)

        self.assertEqual([row["id"] for row in results], [product["id"]])

    def test_category_brand_price_rating_and_stock_filters_combine(self) -> None:
        product = next(
            item for item in self.catalog
            if item["stock"] > 0 and item["category"] and item["brand"]
        )

        results = find_products(
            search_term=product["sku"],
            min_price=product["price"],
            max_price=product["price"],
            min_rating=product["rating_avg"],
            in_stock=True,
            category=product["category"],
            brand=product["brand"],
            limit=1000,
        )

        self.assertEqual([row["id"] for row in results], [product["id"]])

    def test_price_boundaries_include_equal_prices(self) -> None:
        price = self.catalog[0]["price"]
        expected = {
            product["id"]
            for product in self.catalog
            if product["price"] == price
        }

        results = find_products(
            min_price=price,
            max_price=price,
            limit=1000,
        )

        self.assertEqual({product["id"] for product in results}, expected)

    def test_sort_options_reorder_actual_catalog_rows(self) -> None:
        low_to_high = find_products(sort_by="price_low_to_high", limit=1000)
        high_to_low = find_products(sort_by="price_high_to_low", limit=1000)
        highest_rated = find_products(sort_by="highest_rated", limit=1000)
        names = find_products(sort_by="name_ascending", limit=1000)

        self.assertEqual(
            [product["price"] for product in low_to_high],
            sorted(product["price"] for product in self.catalog),
        )
        self.assertEqual(
            [product["price"] for product in high_to_low],
            sorted(
                (product["price"] for product in self.catalog),
                reverse=True,
            ),
        )
        self.assertEqual(
            [product["rating_avg"] for product in highest_rated],
            sorted(
                (product["rating_avg"] for product in self.catalog),
                reverse=True,
            ),
        )
        self.assertEqual(
            [product["name"].casefold() for product in names],
            sorted(product["name"].casefold() for product in self.catalog),
        )

    def test_invalid_price_ranges_and_ratings_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Minimum price"):
            find_products(min_price=500, max_price=100)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            find_products(min_price=-1)
        with self.assertRaisesRegex(ValueError, "between 0 and 5"):
            find_products(min_rating=5.1)

    def test_catalog_facets_and_fresh_product_lookup_use_real_rows(self) -> None:
        facets = get_catalog_facets()
        product = self.catalog[0]

        self.assertIn(product["category"], facets["categories"])
        self.assertIn(product["brand"], facets["brands"])
        self.assertEqual(
            get_products_by_ids([product["id"]]),
            [product],
        )
        self.assertEqual(get_products_by_ids([]), [])

    def test_no_match_returns_an_empty_list(self) -> None:
        self.assertEqual(
            find_products(search_term="__no_shopwise_match__", limit=1000),
            [],
        )

    def test_count_and_offset_pages_match_filtered_sorted_results(self) -> None:
        category = self.catalog[0]["category"]
        expected = find_products(category=category, sort_by="name_ascending", limit=1000)
        self.assertEqual(count_products(category=category), len(expected))

        paged = []
        for offset in range(0, len(expected), 15):
            paged.extend(
                find_products(
                    category=category,
                    sort_by="name_ascending",
                    limit=15,
                    offset=offset,
                )
            )

        self.assertEqual([row["id"] for row in paged], [row["id"] for row in expected])
        self.assertEqual(len({row["id"] for row in paged}), len(expected))

    def test_offset_must_be_a_non_negative_integer(self) -> None:
        with self.assertRaisesRegex(ValueError, "offset"):
            find_products(offset=-1)


if __name__ == "__main__":
    unittest.main()
