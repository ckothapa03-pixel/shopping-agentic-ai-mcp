from collections.abc import Mapping
import math
from decimal import Decimal
from typing import Any


def _product_id_and_stock(product: Mapping[str, Any]) -> tuple[int, int]:
    product_id = product.get("id")
    stock = product.get("stock")
    if isinstance(product_id, bool) or not isinstance(product_id, int):
        raise ValueError("Product id must be an integer")
    if isinstance(stock, bool) or not isinstance(stock, int) or stock < 0:
        raise ValueError("Product stock must be a non-negative integer")
    return product_id, stock


def _validate_quantity(quantity: int, stock: int) -> None:
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise ValueError("Quantity must be a positive integer")
    if quantity > stock:
        raise ValueError("Quantity cannot exceed available stock")


def add_to_cart(
    cart: Mapping[int, int],
    product: Mapping[str, Any],
    quantity: int = 1,
) -> dict[int, int]:
    product_id, stock = _product_id_and_stock(product)
    _validate_quantity(quantity, stock)
    updated = dict(cart)
    new_quantity = updated.get(product_id, 0) + quantity
    _validate_quantity(new_quantity, stock)
    updated[product_id] = new_quantity
    return updated


def update_cart_quantity(
    cart: Mapping[int, int],
    product: Mapping[str, Any],
    quantity: int,
) -> dict[int, int]:
    product_id, stock = _product_id_and_stock(product)
    _validate_quantity(quantity, stock)
    if product_id not in cart:
        raise ValueError("Product is not in the cart")
    updated = dict(cart)
    updated[product_id] = quantity
    return updated


def remove_from_cart(cart: Mapping[int, int], product_id: int) -> dict[int, int]:
    updated = dict(cart)
    updated.pop(product_id, None)
    return updated


def cart_total(
    cart: Mapping[int, int],
    products_by_id: Mapping[int, Mapping[str, Any]],
) -> float:
    total = Decimal("0")
    for product_id, quantity in cart.items():
        product = products_by_id.get(product_id)
        if product is None:
            raise ValueError(f"Product {product_id} is unavailable")
        price = product.get("price")
        if (
            isinstance(price, bool)
            or not isinstance(price, (int, float))
            or not math.isfinite(price)
            or price < 0
        ):
            raise ValueError(f"Product {product_id} has an invalid price")
        _validate_quantity(quantity, product["stock"])
        total += Decimal(str(price)) * quantity
    return float(total)


def validate_checkout(
    cart: Mapping[int, int],
    products_by_id: Mapping[int, Mapping[str, Any]],
) -> float:
    """Recalculate a non-empty cart against fresh products before demo checkout."""
    if not cart:
        raise ValueError("Your cart is empty.")
    return cart_total(cart, products_by_id)
