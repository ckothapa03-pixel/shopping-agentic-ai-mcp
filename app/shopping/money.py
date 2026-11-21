"""Currency conversion and rounding shared by cart and checkout logic."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

CENT = Decimal("0.01")


def money(value: Any) -> Decimal:
    """Convert a SQLite/Python numeric value to cents using half-up rounding."""
    if isinstance(value, bool):
        raise ValueError("A monetary amount must be numeric.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError("A monetary amount must be numeric.") from error
    if not amount.is_finite():
        raise ValueError("A monetary amount must be finite.")
    try:
        return amount.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as error:
        raise ValueError("A monetary amount is outside the supported range.") from error
