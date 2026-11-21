from contextlib import closing
from decimal import Decimal
from typing import Any

from app.db.database import get_connection, get_writable_connection
from app.shopping.coupon_policy import coupon_discount
from app.shopping.money import money


_COUPON_SELECT = """
    SELECT code, discount_percent, min_order_value, max_discount,
           valid_until, is_active,
           valid_until > CURRENT_TIMESTAMP AS is_valid_now
    FROM coupons WHERE code=?
"""


def _normalize_coupon_code(coupon_code: str | None) -> str | None:
    if coupon_code is None:
        return None
    if not isinstance(coupon_code, str):
        raise ValueError("Coupon code is invalid.")
    return coupon_code.strip().upper() or None


def calculate_coupon_discount(subtotal: Decimal, coupon_code: str | None) -> Decimal:
    """Calculate the current coupon discount for the review screen."""
    code = _normalize_coupon_code(coupon_code)
    if code is None:
        return Decimal("0.00")
    with closing(get_connection()) as connection:
        coupon = connection.execute(_COUPON_SELECT, (code,)).fetchone()
    return coupon_discount(money(subtotal), coupon)


def _current_cart_snapshot(cart_rows: list[Any], prices: dict[int, Decimal]) -> list[tuple[int, int, str]]:
    return sorted(
        (int(row["product_id"]), int(row["quantity"]), str(prices[int(row["product_id"])]))
        for row in cart_rows
    )


def _normalize_expected_cart(expected_cart: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    try:
        normalized = []
        for item in expected_cart:
            if not isinstance(item, (tuple, list)) or len(item) != 3:
                raise ValueError
            product_id, quantity, price = item
            if (
                isinstance(product_id, bool)
                or not isinstance(product_id, int)
                or isinstance(quantity, bool)
                or not isinstance(quantity, int)
                or quantity < 1
            ):
                raise ValueError
            unit_price = money(price)
            if unit_price < 0:
                raise ValueError
            normalized.append((product_id, quantity, str(unit_price)))
        return sorted(normalized)
    except (TypeError, ValueError) as error:
        raise ValueError("Checkout confirmation is invalid. Review checkout again.") from error


def create_order(
    user_id: str,
    address_id: int,
    payment_method: str = "COD",
    coupon_code: str | None = None,
    expected_cart: list[tuple[int, int, str]] | None = None,
    expected_total: Decimal | None = None,
) -> dict[str, Any]:
    coupon_code = _normalize_coupon_code(coupon_code)
    if isinstance(address_id, bool) or not isinstance(address_id, int) or address_id < 1:
        raise ValueError("A valid delivery address is required.")
    if not isinstance(payment_method, str) or not payment_method.strip():
        raise ValueError("Payment method is required")

    with closing(get_writable_connection()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = connection.execute(
            "SELECT user_id FROM users WHERE user_id=? AND is_active=1",
            (user_id,),
        ).fetchone()
        if user is None:
            raise PermissionError("The shopping identity is inactive or unavailable.")
        address = connection.execute(
            "SELECT id FROM addresses WHERE id=? AND user_id=?",
            (address_id, user_id),
        ).fetchone()
        if address is None:
            raise PermissionError("A valid owned delivery address is required.")
        cart_rows = connection.execute(
            "SELECT product_id, quantity FROM cart_items WHERE user_id=?",
            (user_id,),
        ).fetchall()
        if not cart_rows:
            raise ValueError("Your cart is empty.")
        product_ids = [row["product_id"] for row in cart_rows]
        placeholders = ", ".join("?" for _ in product_ids)
        products = connection.execute(
            f"SELECT id, price, stock FROM products WHERE id IN ({placeholders})",
            product_ids,
        ).fetchall()
        product_by_id = {int(product["id"]): product for product in products}
        if len(product_by_id) != len(product_ids):
            raise ValueError("A cart product is no longer available.")
        unit_prices = {
            product_id: money(product["price"])
            for product_id, product in product_by_id.items()
        }
        if any(price < 0 for price in unit_prices.values()):
            raise ValueError("A cart product has an invalid price.")
        if expected_cart is not None:
            current_cart = _current_cart_snapshot(cart_rows, unit_prices)
            if current_cart != _normalize_expected_cart(expected_cart):
                raise ValueError("Your cart changed. Review checkout again.")

        subtotal = Decimal("0.00")
        for row in cart_rows:
            product = product_by_id.get(row["product_id"])
            quantity = row["quantity"]
            if product is None:
                raise ValueError("A cart product is no longer available.")
            if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
                raise ValueError("Invalid cart quantity.")
            stock = product["stock"]
            if isinstance(stock, bool) or not isinstance(stock, int) or stock < 0:
                raise ValueError("A cart product has invalid inventory.")
            if quantity > stock:
                raise ValueError("Cart quantity exceeds current stock.")
            subtotal += unit_prices[int(row["product_id"])] * quantity
        subtotal = money(subtotal)

        discount = Decimal("0.00")
        if coupon_code:
            coupon = connection.execute(_COUPON_SELECT, (coupon_code,)).fetchone()
            discount = coupon_discount(subtotal, coupon)

        shipping_fee = Decimal("0.00")
        total = money(subtotal - discount + shipping_fee)
        if expected_total is not None:
            try:
                total_approved = money(expected_total)
            except ValueError as error:
                raise ValueError("Checkout confirmation is invalid. Review checkout again.") from error
            if total != total_approved:
                raise ValueError("The checkout total changed. Review checkout again.")
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
                coupon_code,
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
                (
                    order_id,
                    row["product_id"],
                    row["quantity"],
                    float(unit_prices[int(row["product_id"])]),
                ),
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
