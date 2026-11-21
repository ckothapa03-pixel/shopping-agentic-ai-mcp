from contextlib import closing
from typing import Any

from app.db.database import get_writable_connection
from app.db.database import get_connection
from app.db.products import get_products_by_ids


def ensure_active_user(user_id: str) -> None:
    with closing(get_connection()) as connection:
        row = connection.execute(
            "SELECT user_id FROM users WHERE user_id=? AND is_active=1",
            (user_id,),
        ).fetchone()
    if row is None:
        raise PermissionError("The shopping identity is inactive or unavailable.")


def get_cart(user_id: str) -> list[dict[str, Any]]:
    ensure_active_user(user_id)
    with closing(get_connection()) as connection:
        rows = connection.execute(
            "SELECT product_id, quantity FROM cart_items WHERE user_id=?",
            (user_id,),
        ).fetchall()
    products = get_products_by_ids([row["product_id"] for row in rows])
    product_by_id = {row["id"]: row for row in products}
    return [
        {
            "product_id": row["product_id"],
            "quantity": row["quantity"],
            "product": product_by_id.get(row["product_id"]),
        }
        for row in rows
    ]


def set_cart_quantity(user_id: str, product_id: int, quantity: int) -> None:
    ensure_active_user(user_id)
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise ValueError("Quantity must be a positive integer")
    products = get_products_by_ids([product_id])
    if not products:
        raise ValueError("This product is no longer available.")
    if quantity > int(products[0]["stock"]):
        raise ValueError("Quantity cannot exceed available stock")
    with closing(get_writable_connection()) as connection:
        connection.execute(
            """
            INSERT INTO cart_items (user_id, product_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, product_id)
            DO UPDATE SET quantity=excluded.quantity
            """,
            (user_id, product_id, quantity),
        )
        connection.commit()


def remove_cart_item(user_id: str, product_id: int) -> None:
    ensure_active_user(user_id)
    with closing(get_writable_connection()) as connection:
        connection.execute(
            "DELETE FROM cart_items WHERE user_id=? AND product_id=?",
            (user_id, product_id),
        )
        connection.commit()


def clear_cart(user_id: str) -> None:
    ensure_active_user(user_id)
    with closing(get_writable_connection()) as connection:
        connection.execute("DELETE FROM cart_items WHERE user_id=?", (user_id,))
        connection.commit()


def get_wishlist(user_id: str) -> list[dict[str, Any]]:
    ensure_active_user(user_id)
    with closing(get_connection()) as connection:
        rows = connection.execute(
            "SELECT product_id FROM wishlists WHERE user_id=? ORDER BY added_at",
            (user_id,),
        ).fetchall()
    products = get_products_by_ids([row["product_id"] for row in rows])
    return products


def set_wishlist(user_id: str, product_id: int, saved: bool) -> None:
    ensure_active_user(user_id)
    with closing(get_writable_connection()) as connection:
        if saved:
            connection.execute(
                """
                INSERT OR IGNORE INTO wishlists (user_id, product_id)
                VALUES (?, ?)
                """,
                (user_id, product_id),
            )
        else:
            connection.execute(
                "DELETE FROM wishlists WHERE user_id=? AND product_id=?",
                (user_id, product_id),
            )
        connection.commit()
