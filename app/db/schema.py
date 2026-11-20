import sqlite3
from contextlib import closing

from app.db.database import DB_PATH


def initialize_shopping_schema() -> None:
    """Create only approved additive tables/indexes; never modify existing rows."""
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS wishlists (
                user_id TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, product_id)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wishlists_user
            ON wishlists (user_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_orders_user_created
            ON orders (user_id, created_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_orders_status
            ON orders (status)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_order_items_order
            ON order_items (order_id)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_documents (
                id INTEGER PRIMARY KEY,
                source_name TEXT NOT NULL UNIQUE,
                document_type TEXT NOT NULL,
                content TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id INTEGER PRIMARY KEY,
                document_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                UNIQUE(document_id, chunk_index)
            )
            """
        )
        connection.commit()
