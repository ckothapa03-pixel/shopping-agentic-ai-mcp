import os
import sys
import time

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

    started_at = time.perf_counter()
    outcome = "failed"
    try:
        products = find_products(
            search_term=search_term,
            max_price=max_price,
            min_rating=min_rating,
            in_stock=in_stock,
            limit=limit,
        )
        outcome = "completed"
        return products
    finally:
        if os.getenv("SHOPWISE_CHAT_TIMING", "").strip().casefold() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            elapsed = time.perf_counter() - started_at
            print(
                "Shopwise chat timing "
                f"stage=sqlite_product_search outcome={outcome} "
                f"elapsed_seconds={elapsed:.3f}",
                file=sys.stderr,
                flush=True,
            )
