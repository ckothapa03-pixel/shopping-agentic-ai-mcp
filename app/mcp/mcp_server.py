import sys
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from app.agent.tool_permissions import require_explicit_confirmation

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.tools.products_tool import search_products as search_products_from_db
from app.db.products import (
    get_product_details as get_product_details_from_db,
    get_similar_products as get_similar_products_from_db,
    get_products_by_ids,
)
from app.db.user_data import (
    clear_cart as clear_cart_from_db,
    get_cart,
    get_wishlist,
    remove_cart_item,
    set_cart_quantity,
    set_wishlist as set_wishlist_from_db,
)
from app.db.address_repository import list_addresses
from app.db.order_repository import list_orders, get_order
from app.db.checkout_repository import create_order
from app.rag.retrieval import retrieve_chunks
from app.db.address_repository import list_addresses


mcp = FastMCP("Shopping Assistant")

_session_user_id: str | None = None
_session_user_id = os.getenv("SHOPWISE_USER_ID") or None


def set_mcp_user_id(user_id: str | None) -> None:
    global _session_user_id
    _session_user_id = user_id


def _require_mcp_user() -> str:
    if not _session_user_id:
        raise PermissionError("Authentication is required.")
    return _session_user_id


@mcp.tool()
def search_products(
    search_term: str = "",
    max_price: float | None = None,
    min_rating: float | None = None,
    in_stock: bool = False,
    limit: int = 20,
) -> list[dict]:
    """
    Search products in the local shopping database.

    Args:
        search_term: Product name, keyword, SKU, brand, or category.
        max_price: Optional maximum selling price.
        min_rating: Optional minimum average rating.
        in_stock: If true, only return products with stock greater than zero.
        limit: Maximum number of products to return.
    """
    return search_products_from_db(
        search_term=search_term,
        max_price=max_price,
        min_rating=min_rating,
        in_stock=in_stock,
        limit=limit,
    )


@mcp.tool()
def get_product_details(product_id: int) -> dict | None:
    """Return one verified database product or none."""
    return get_product_details_from_db(product_id)


@mcp.tool()
def get_categories() -> list[str]:
    from app.db.products import get_catalog_facets
    return get_catalog_facets()["categories"]


@mcp.tool()
def get_brands() -> list[str]:
    from app.db.products import get_catalog_facets
    return get_catalog_facets()["brands"]


@mcp.tool()
def compare_products(product_ids: list[int]) -> list[dict]:
    if len(product_ids) < 2 or len(product_ids) > 4:
        raise ValueError("Compare between 2 and 4 products")
    if len(set(product_ids)) != len(product_ids):
        raise ValueError("Product ids must be unique")
    return get_products_by_ids(product_ids)


@mcp.tool()
def get_similar_products(product_id: int, limit: int = 6) -> list[dict]:
    return get_similar_products_from_db(product_id, limit)


@mcp.tool()
def add_to_cart(product_id: int, quantity: int = 1) -> dict:
    user_id = _require_mcp_user()
    require_explicit_confirmation("add_to_cart")
    set_cart_quantity(user_id, product_id, quantity)
    return {"cart": get_cart(user_id)}


@mcp.tool()
def view_cart() -> list[dict]:
    return get_cart(_require_mcp_user())


@mcp.tool()
def update_cart_quantity(product_id: int, quantity: int) -> dict:
    user_id = _require_mcp_user()
    require_explicit_confirmation("update_cart_quantity")
    set_cart_quantity(user_id, product_id, quantity)
    return {"cart": get_cart(user_id)}


@mcp.tool()
def remove_from_cart(product_id: int) -> dict:
    user_id = _require_mcp_user()
    require_explicit_confirmation("remove_from_cart")
    remove_cart_item(user_id, product_id)
    return {"cart": get_cart(user_id)}


@mcp.tool()
def clear_cart() -> dict:
    user_id = _require_mcp_user()
    require_explicit_confirmation("clear_cart")
    clear_cart_from_db(user_id)
    return {"cart": []}


@mcp.tool()
def view_wishlist() -> list[dict]:
    return get_wishlist(_require_mcp_user())


@mcp.tool()
def set_wishlist(product_id: int, saved: bool) -> dict:
    user_id = _require_mcp_user()
    require_explicit_confirmation("set_wishlist")
    set_wishlist_from_db(user_id, product_id, saved)
    return {"wishlist": get_wishlist(user_id)}


@mcp.tool()
def get_addresses() -> list[dict]:
    return list_addresses(_require_mcp_user())


@mcp.tool()
def get_orders(status: str | None = None, limit: int = 20, offset: int = 0) -> list[dict]:
    return list_orders(_require_mcp_user(), status, limit, offset)


@mcp.tool()
def get_order_details(order_id: int) -> dict | None:
    return get_order(_require_mcp_user(), order_id)


@mcp.tool()
def track_order(order_id: int) -> dict:
    detail = get_order(_require_mcp_user(), order_id)
    if detail is None:
        raise PermissionError("Order not found.")
    return {"order_id": detail["order"]["id"], "status": detail["order"]["status"]}


@mcp.tool()
def create_checkout_order(address_id: int, payment_method: str = "COD", coupon_code: str | None = None) -> dict:
    user_id = _require_mcp_user()
    require_explicit_confirmation("create_checkout_order")
    return create_order(user_id, address_id, payment_method, coupon_code)


@mcp.tool()
def cancel_order(order_id: int) -> dict:
    from app.db.order_repository import cancel_order as cancel_owned_order
    user_id = _require_mcp_user()
    require_explicit_confirmation("cancel_order")
    detail = cancel_owned_order(user_id, order_id)
    return detail


@mcp.tool()
def get_user_profile() -> dict:
    from app.db.identity import resolve_shopping_user_by_id
    user_id = _require_mcp_user()
    profile = resolve_shopping_user_by_id(user_id)
    if profile is None:
        raise PermissionError("Profile not found.")
    return {
        "user_id": profile["user_id"],
        "full_name": profile["full_name"],
        "email": profile["email"],
    }


@mcp.tool()
def search_policies(query: str, limit: int = 5) -> list[dict]:
    return retrieve_chunks(query, limit)


if __name__ == "__main__":
    from app.observability import configure_logging
    configure_logging()
    import logging
    logging.getLogger("app.mcp").info("event=mcp_server_started")
    mcp.run()
