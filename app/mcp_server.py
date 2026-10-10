import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.tools.products_tool import search_products as search_products_from_db


mcp = FastMCP("Shopping Assistant")


@mcp.tool()
def search_products(
    search_term: str,
    max_price: float | None = None,
    min_rating: float | None = None,
    in_stock: bool = False,
) -> list[dict]:
    """
    Search products in the local shopping database.

    Args:
        search_term: Product name, keyword, SKU, brand, or category.
        max_price: Optional maximum selling price.
        min_rating: Optional minimum average rating.
        in_stock: If true, only return products with stock greater than zero.
    """
    return search_products_from_db(
        search_term=search_term,
        max_price=max_price,
        min_rating=min_rating,
        in_stock=in_stock,
    )


if __name__ == "__main__":
    mcp.run()
