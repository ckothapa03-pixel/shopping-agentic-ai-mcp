import re
from typing import Any

BUDGET_INTENT = re.compile(r"\b(?:budget|afford\w*)\b", re.IGNORECASE)
BUDGET_AMOUNT = re.compile(
    r"(?:₹|rs\.?|inr)\s*\d"
    r"|\b(?:budget|afford\w*)\D{0,24}\d"
    r"|\b(?:under|below|up to|less than|maximum|max)\D{0,12}\d",
    re.IGNORECASE,
)
BUDGET_CLARIFICATION = "What is your maximum budget in rupees?"


def needs_budget_clarification(message: str) -> bool:
    return bool(BUDGET_INTENT.search(message) and not BUDGET_AMOUNT.search(message))


def format_product_results(products: list[dict[str, Any]]) -> str:
    if not products:
        return "Catalog results from shopping.db:\nNo matching products found."
    lines = ["Catalog results from shopping.db:"]
    for product in products:
        price = product.get("price")
        price_text = (
            f"₹{price:,.2f}"
            if isinstance(price, (int, float)) and not isinstance(price, bool)
            else "unavailable"
        )
        rating = product.get("rating_avg")
        rating_text = f"{rating}/5" if rating is not None else "unrated"
        stock = product.get("stock")
        availability = (
            f"In stock ({stock})"
            if isinstance(stock, (int, float)) and stock > 0
            else "Out of stock"
        )
        lines.append(
            f"- {product.get('name') or 'Unnamed product'} | {price_text} | "
            f"Rating: {rating_text} | {availability} | "
            f"Brand: {product.get('brand') or '—'} | "
            f"Category: {product.get('category') or '—'}"
        )
    return "\n".join(lines)
