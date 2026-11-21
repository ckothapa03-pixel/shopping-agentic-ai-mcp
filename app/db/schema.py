import sqlite3
from contextlib import closing

from app.db.database import DB_PATH
from pathlib import Path
import os

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


def _account_database_path() -> Path:
    configured = os.environ.get("SHOPPING_AUTH_DB")
    return Path(configured).resolve() if configured else DB_PATH.parent / "accounts.sqlite3"


def validate_shopping_schema() -> None:
    """Verify required existing tables without creating or altering anything."""
    if not DB_PATH.is_file():
        raise FileNotFoundError(f"Shopping database not found: {DB_PATH}")
    with closing(sqlite3.connect(f"{DB_PATH.resolve().as_uri()}?mode=ro", uri=True)) as connection:
        existing = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    missing = sorted(REQUIRED_SHOPPING_TABLES - existing)
    if missing:
        raise RuntimeError(
            "Required shopping table(s) not found: " + ", ".join(missing)
        )


def validate_account_schema() -> None:
    """Verify required existing account tables without creating anything."""
    account_db = _account_database_path()
    if not account_db.is_file():
        raise FileNotFoundError(f"Accounts database not found: {account_db}")
    uri = f"{account_db.as_uri()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        existing = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    missing = sorted(REQUIRED_ACCOUNT_TABLES - existing)
    if missing:
        raise RuntimeError(
            "Required account table(s) not found: " + ", ".join(missing)
        )
