from contextlib import closing
from typing import Any

from app.db.database import get_connection, get_writable_connection
from app.db.user_data import ensure_active_user


def list_orders(user_id: str, status: str | None = None, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
    ensure_active_user(user_id)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("Limit must be a positive integer")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("Offset must be non-negative")
    clause = " WHERE user_id=?"
    params: list[Any] = [user_id]
    if status:
        clause += " AND status=?"
        params.append(status)
    params.extend([limit, offset])
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT id,user_id,address_id,status,payment_method,coupon_code,
                   subtotal,discount,shipping_fee,total,created_at
            FROM orders
            """ + clause + " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def get_order(user_id: str, order_id: int) -> dict[str, Any] | None:
    ensure_active_user(user_id)
    with closing(get_connection()) as connection:
        order = connection.execute(
            """
            SELECT id,user_id,address_id,status,payment_method,coupon_code,
                   subtotal,discount,shipping_fee,total,created_at
            FROM orders
            WHERE id=? AND user_id=?
            """,
            (order_id, user_id),
        ).fetchone()
        if order is None:
            return None
        items = connection.execute(
            """
            SELECT oi.id,oi.product_id,p.name,p.sku,oi.quantity,oi.unit_price
            FROM order_items oi
            LEFT JOIN products p ON p.id=oi.product_id
            WHERE oi.order_id=?
            """,
            (order_id,),
        ).fetchall()
        address = connection.execute(
            """
            SELECT id,label,line1,city,state,pincode,is_default
            FROM addresses
            WHERE id=? AND user_id=?
            """,
            (order["address_id"], user_id),
        ).fetchone() if order["address_id"] is not None else None
    return {
        "order": dict(order),
        "items": [dict(row) for row in items],
        "address": dict(address) if address else None,
    }


def cancel_order(user_id: str, order_id: int) -> dict[str, Any]:
    ensure_active_user(user_id)
    with closing(get_writable_connection()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        order = connection.execute(
            "SELECT id,status FROM orders WHERE id=? AND user_id=?",
            (order_id, user_id),
        ).fetchone()
        if order is None:
            raise PermissionError("Order not found.")
        if order["status"] not in {"PLACED", "CONFIRMED"}:
            raise ValueError("This order cannot be cancelled.")
        items = connection.execute(
            "SELECT product_id, quantity FROM order_items WHERE order_id=?",
            (order_id,),
        ).fetchall()
        for item in items:
            connection.execute(
                "UPDATE products SET stock=stock+? WHERE id=?",
                (item["quantity"], item["product_id"]),
            )
        connection.execute(
            "UPDATE orders SET status='CANCELLED' WHERE id=? AND user_id=?",
            (order_id, user_id),
        )
        connection.commit()
    return get_order(user_id, order_id)["order"]
