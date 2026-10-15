from app.db.products import find_products


def search_products(
    search_term: str = "",
    max_price: float | None = None,
    min_rating: float | None = None,
    in_stock: bool = False,
    limit: int = 20,
) -> list[dict]:
    """Clean application-level interface for product search."""
    if limit is None:
        limit = 20
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive integer")

    return find_products(
        search_term=search_term,
        max_price=max_price,
        min_rating=min_rating,
        in_stock=in_stock,
        limit=limit,
    )
