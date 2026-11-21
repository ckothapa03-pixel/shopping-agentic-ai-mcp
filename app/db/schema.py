import os
from contextlib import closing
from pathlib import Path

from app.db.database import DB_PATH, connect_readonly

REQUIRED_SHOPPING_TABLES = {
    "addresses",
    "brands",
    "cart_items",
    "categories",
    "coupons",
    "order_items",
    "orders",
    "products",
    "rag_chunks",
    "rag_documents",
    "reviews",
    "users",
    "wishlists",
}

REQUIRED_ACCOUNT_TABLES = {"accounts", "identity_mappings"}
REQUIRED_SHOPPING_COLUMNS = {
    "addresses": {"id", "user_id", "label", "line1", "city", "state", "pincode", "is_default"},
    "brands": {"id", "name"},
    "cart_items": {"user_id", "product_id", "quantity", "added_at"},
    "categories": {"id", "name", "slug", "description"},
    "coupons": {"code", "discount_percent", "min_order_value", "max_discount", "valid_until", "is_active"},
    "order_items": {"id", "order_id", "product_id", "quantity", "unit_price"},
    "orders": {"id", "user_id", "address_id", "status", "payment_method", "coupon_code", "subtotal", "discount", "shipping_fee", "total", "created_at"},
    "products": {"id", "sku", "name", "description", "price", "mrp", "stock", "rating_avg", "rating_count", "category_id", "brand_id", "created_at"},
    "rag_chunks": {"id", "document_id", "chunk_index", "chunk_text"},
    "rag_documents": {"id", "source_name", "document_type", "content", "updated_at"},
    "reviews": {"id", "product_id", "user_id", "rating", "title", "body", "created_at"},
    "users": {"user_id", "full_name", "email", "phone", "created_at", "is_active"},
    "wishlists": {"user_id", "product_id", "added_at"},
}
REQUIRED_ACCOUNT_COLUMNS = {
    "accounts": {"email", "full_name", "password_salt", "password_hash", "created_at"},
    "identity_mappings": {"account_email", "user_id", "created_at"},
}


def _account_database_path() -> Path:
    configured = os.environ.get("SHOPPING_AUTH_DB")
    return Path(configured).resolve() if configured else DB_PATH.parent / "accounts.sqlite3"


def _validate_database(path: Path, required_columns: dict[str, set[str]]) -> None:
    with closing(connect_readonly(path)) as connection:
        existing = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        missing = sorted(required_columns.keys() - existing)
        if missing:
            raise RuntimeError(
                "Required database table(s) not found: " + ", ".join(missing)
            )
        missing_columns = []
        for table, required in required_columns.items():
            actual = {
                row[1]
                for row in connection.execute(f'PRAGMA table_info("{table}")')
            }
            absent = sorted(required - actual)
            if absent:
                missing_columns.append(f"{table} ({', '.join(absent)})")
        if missing_columns:
            raise RuntimeError(
                "Required database column(s) not found: " + "; ".join(missing_columns)
            )


def validate_shopping_schema() -> None:
    """Verify existing shopping tables and columns without modifying the file."""
    if REQUIRED_SHOPPING_TABLES != REQUIRED_SHOPPING_COLUMNS.keys():
        raise RuntimeError("Shopping schema validation policy is incomplete.")
    _validate_database(DB_PATH, REQUIRED_SHOPPING_COLUMNS)


def validate_account_schema() -> None:
    """Verify required existing account tables without creating anything."""
    account_db = _account_database_path()
    if REQUIRED_ACCOUNT_TABLES != REQUIRED_ACCOUNT_COLUMNS.keys():
        raise RuntimeError("Account schema validation policy is incomplete.")
    _validate_database(account_db, REQUIRED_ACCOUNT_COLUMNS)
