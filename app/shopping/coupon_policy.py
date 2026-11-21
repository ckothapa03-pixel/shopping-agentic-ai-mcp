"""Checkout coupon validation and discount calculation."""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.shopping.money import money

_SQLITE_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def validate_coupon_timestamp(value: Any) -> None:
    try:
        datetime.strptime(str(value), _SQLITE_TIMESTAMP_FORMAT)
    except (TypeError, ValueError) as error:
        raise ValueError("Coupon validity is unavailable.") from error


def coupon_discount(subtotal: Decimal, coupon: Mapping[str, Any] | None) -> Decimal:
    if coupon is None:
        raise ValueError("Coupon is invalid.")
    if not coupon["is_active"]:
        raise ValueError("Coupon is inactive.")
    validate_coupon_timestamp(coupon["valid_until"])
    if not coupon["is_valid_now"]:
        raise ValueError("Coupon has expired.")

    try:
        percent = Decimal(str(coupon["discount_percent"]))
        minimum = money(coupon["min_order_value"])
        maximum = money(coupon["max_discount"])
    except (InvalidOperation, KeyError, TypeError, ValueError) as error:
        raise ValueError("Coupon configuration is invalid.") from error
    if not percent.is_finite() or not Decimal("0") <= percent <= Decimal("100"):
        raise ValueError("Coupon configuration is invalid.")
    if minimum < 0 or maximum < 0:
        raise ValueError("Coupon configuration is invalid.")

    eligible_subtotal = money(subtotal)
    if eligible_subtotal < minimum:
        raise ValueError("Coupon minimum order value is not met.")
    calculated = money(eligible_subtotal * percent / Decimal("100"))
    return min(calculated, maximum, eligible_subtotal)
