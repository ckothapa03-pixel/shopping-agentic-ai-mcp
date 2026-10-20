import math
from contextlib import closing
from typing import Any

from app.db.database import get_connection


_PRODUCT_SELECT = """
    SELECT
        p.id,
        p.sku,
        p.name,
        p.description,
        p.price,
        p.mrp,
        p.stock,
        p.rating_avg,
        p.rating_count,
        c.name AS category,
        b.name AS brand
    FROM products p
    LEFT JOIN categories c ON c.id = p.category_id
    LEFT JOIN brands b ON b.id = p.brand_id
"""
_SORT_ORDERS = {
    "relevance": "p.rating_avg DESC, p.rating_count DESC, p.price ASC",
    "price_low_to_high": "p.price ASC, p.id ASC",
    "price_high_to_low": "p.price DESC, p.id ASC",
    "highest_rated": "p.rating_avg DESC, p.rating_count DESC, p.price ASC",
    "name_ascending": "p.name COLLATE NOCASE ASC, p.id ASC",
}


def _is_finite_number(value: int | float) -> bool:
    try:
        return math.isfinite(float(value))
    except (OverflowError, TypeError, ValueError):
        return False


def find_products(
    search_term: str = "",
    max_price: float | None = None,
    min_rating: float | None = None,
    in_stock: bool = False,
    limit: int = 20,
    min_price: float | None = None,
    category: str | None = None,
    brand: str | None = None,
    sort_by: str = "relevance",
) -> list[dict]:
    """
    Search products in the local shopping database.

    Search checks product name and description.
    Optional filters:
      - max_price
      - min_rating
      - in_stock
    """
    if search_term is None:
        search_term = ""
    if not isinstance(search_term, str):
        raise ValueError("search_term must be a string")
    search_term = search_term.strip()

    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive integer")
    if not isinstance(sort_by, str) or sort_by not in _SORT_ORDERS:
        raise ValueError("Unsupported product sort order")
    for label, value in (("min_price", min_price), ("max_price", max_price)):
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not _is_finite_number(value)
            or value < 0
        ):
            raise ValueError(f"{label} must be a non-negative number")
    if min_price is not None and max_price is not None and min_price > max_price:
        raise ValueError("Minimum price cannot exceed maximum price")
    if min_rating is not None and (
        isinstance(min_rating, bool)
        or not isinstance(min_rating, (int, float))
        or not _is_finite_number(min_rating)
        or not 0 <= min_rating <= 5
    ):
        raise ValueError("Minimum rating must be between 0 and 5")
    if not isinstance(in_stock, bool):
        raise ValueError("in_stock must be a boolean")
    for label, value in (("category", category), ("brand", brand)):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{label} must be a non-empty string")

    query = _PRODUCT_SELECT + " WHERE 1 = 1"

    params = []

    if search_term:
        query += """
            AND (
                LOWER(p.name) LIKE LOWER(?)
                OR LOWER(p.description) LIKE LOWER(?)
                OR LOWER(p.sku) LIKE LOWER(?)
                OR LOWER(COALESCE(b.name, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(c.name, '')) LIKE LOWER(?)
            )
        """
        term = f"%{search_term}%"
        params.extend([term, term, term, term, term])

    if max_price is not None:
        query += " AND p.price <= ?"
        params.append(max_price)

    if min_price is not None:
        query += " AND p.price >= ?"
        params.append(min_price)

    if min_rating is not None:
        query += " AND p.rating_avg >= ?"
        params.append(min_rating)

    if in_stock:
        query += " AND p.stock > 0"

    if category is not None:
        query += " AND c.name = ?"
        params.append(category.strip())

    if brand is not None:
        query += " AND b.name = ?"
        params.append(brand.strip())

    query += f" ORDER BY {_SORT_ORDERS[sort_by]} LIMIT ?"
    params.append(limit)

    with closing(get_connection()) as connection:
        rows = connection.execute(query, params).fetchall()

    return [dict(row) for row in rows]


def get_catalog_facets() -> dict[str, list[str]]:
    """Return category and brand names used by the real product catalog."""
    with closing(get_connection()) as connection:
        categories = connection.execute(
            """
            SELECT DISTINCT c.name
            FROM categories c
            JOIN products p ON p.category_id = c.id
            ORDER BY c.name COLLATE NOCASE
            """
        ).fetchall()
        brands = connection.execute(
            """
            SELECT DISTINCT b.name
            FROM brands b
            JOIN products p ON p.brand_id = b.id
            ORDER BY b.name COLLATE NOCASE
            """
        ).fetchall()
    return {
        "categories": [row["name"] for row in categories],
        "brands": [row["name"] for row in brands],
    }


def get_products_by_ids(product_ids: list[int]) -> list[dict[str, Any]]:
    """Fetch fresh catalog rows for cart validation without reading customer data."""
    if not product_ids:
        return []
    if any(
        isinstance(product_id, bool)
        or not isinstance(product_id, int)
        or product_id < 1
        for product_id in product_ids
    ):
        raise ValueError("Product ids must be positive integers")

    placeholders = ", ".join("?" for _ in product_ids)
    query = _PRODUCT_SELECT + f" WHERE p.id IN ({placeholders})"
    with closing(get_connection()) as connection:
        rows = connection.execute(query, product_ids).fetchall()
    return [dict(row) for row in rows]
