from typing import Any

from app.db.products import find_products


def recommend_products(
    category: str | None = None,
    brand: str | None = None,
    max_price: float | None = None,
    limit: int = 6,
) -> list[dict[str, Any]]:
    """Return deterministic catalog-ranked recommendations."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("Limit must be a positive integer")
    return find_products(
        category=category,
        brand=brand,
        max_price=max_price,
        in_stock=True,
        sort_by="highest_rated",
        limit=limit,
    )
