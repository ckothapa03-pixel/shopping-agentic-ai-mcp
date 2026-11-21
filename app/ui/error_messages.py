"""Safe, concise UI messages for expected errors and internal failures."""

import sqlite3

from app.observability import log_failure


def safe_error_message(
    error: Exception,
    fallback: str,
    *,
    event: str = "ui_operation_failed",
    allow_value_error: bool = False,
) -> str:
    """Preserve safe validation messages; hide internal exception details."""
    if isinstance(error, ValueError) and allow_value_error:
        return str(error)
    log_failure(event, error)
    if isinstance(error, PermissionError):
        return "You are not authorized to perform this action."
    if isinstance(error, (sqlite3.Error, OSError)):
        return fallback
    return fallback
