from decimal import Decimal
from contextlib import closing
from typing import Any

from app.db.database import get_writable_connection
from app.db.address_repository import get_address
from app.db.products import get_products_by_ids
from app.db.user_data import ensure_active_user


def create_order(user_id: str, address_id: int, payment_method: str = "COD", coupon_code: str | None = None) -> dict[str, Any]:
    ensure_active_user(user_id)
    address = get_address(user_id, address_id)
    if address is None:
        raise PermissionError("A valid owned delivery address is required.")
    if not isinstance(payment_method, str) or not payment_method.strip():
        raise ValueError("Payment method is required")

    with closing(get_writable_connection()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cart_rows = connection.execute(
            "SELECT product_id, quantity FROM cart_items WHERE user_id=?",
            (user_id,),
        ).fetchall()
        if not cart_rows:
            raise ValueError("Your cart is empty.")

        product_ids = [row["product_id"] for row in cart_rows]
        products = get_products_by_ids(product_ids)
        product_by_id = {product["id"]: product for product in products}

        subtotal = Decimal("0")
        for row in cart_rows:
            product = product_by_id.get(row["product_id"])
            quantity = row["quantity"]
            if product is None:
                raise ValueError("A cart product is no longer available.")
            if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
                raise ValueError("Invalid cart quantity.")
            if quantity > int(product["stock"]):
                raise ValueError("Cart quantity exceeds current stock.")
            subtotal += Decimal(str(product["price"])) * quantity

        discount = Decimal("0")
        if coupon_code:
            coupon = connection.execute(
                """
                SELECT code, discount_percent, min_order_value, max_discount,
                       valid_until, is_active
                FROM coupons
                WHERE code=? AND is_active=1
                """,
                (coupon_code.strip().upper(),),
            ).fetchone()
            if coupon is None:
                raise ValueError("Coupon is invalid or inactive.")
            if subtotal < Decimal(str(coupon["min_order_value"])):
                raise ValueError("Coupon minimum order value is not met.")
            discount = subtotal * Decimal(coupon["discount_percent"]) / Decimal("100")
            maximum = Decimal(str(coupon["max_discount"]))
            discount = min(discount, maximum)

        shipping_fee = Decimal("0")
        total = subtotal - discount + shipping_fee
        cursor = connection.execute(
            """
            INSERT INTO orders
                (user_id,address_id,status,payment_method,coupon_code,
                 subtotal,discount,shipping_fee,total,created_at)
            VALUES (?, ?, 'PLACED', ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                address_id,
                payment_method.strip(),
                coupon_code.strip().upper() if coupon_code else None,
                float(subtotal),
                float(discount),
                float(shipping_fee),
                float(total),
            ),
        )
        order_id = int(cursor.lastrowid)

        for row in cart_rows:
            product = product_by_id[row["product_id"]]
            connection.execute(
                """
                INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
                """,
                (order_id, row["product_id"], row["quantity"], product["price"]),
            )
            updated = connection.execute(
                """
                UPDATE products
                SET stock=stock-?
                WHERE id=? AND stock>=?
                """,
                (row["quantity"], row["product_id"], row["quantity"]),
            )
            if updated.rowcount != 1:
                raise ValueError("Stock changed during checkout.")

        connection.execute("DELETE FROM cart_items WHERE user_id=?", (user_id,))
        connection.commit()

    return {
        "order_id": order_id,
        "subtotal": float(subtotal),
        "discount": float(discount),
        "shipping_fee": float(shipping_fee),
        "total": float(total),
        "status": "PLACED",
    }
