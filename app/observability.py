"""Privacy-conscious application logging helpers."""

import logging
import os
import re
import traceback


def configure_logging() -> None:
    """Configure application logging once with a conservative default."""
    level = getattr(logging, os.getenv("SHOPWISE_LOG_LEVEL", "INFO").upper(), None)
    if not isinstance(level, int):
        level = logging.INFO
    root = logging.getLogger("app")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False


def error_category(error: BaseException) -> str:
    """Return a coarse category without inspecting exception text."""
    import sqlite3

    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, PermissionError):
        return "authorization"
    if isinstance(error, sqlite3.Error):
        return "database"
    if isinstance(error, OSError):
        return "filesystem"
    if isinstance(error, ValueError):
        return "validation"
    return "unexpected"


def log_failure(event: str, error: BaseException, *, level: int = 40) -> None:
    """Log exception type and safe traceback locations, never exception text."""
    frames = traceback.extract_tb(error.__traceback__) if error.__traceback__ else []
    location = ">".join(f"{os.path.basename(f.filename)}:{f.lineno}" for f in frames[-3:])
    safe_event = re.sub(r"[^a-zA-Z0-9_.-]", "_", event)[:64]
    logging.getLogger("app").log(
        level,
        "event=%s category=%s exception_type=%s location=%s",
        safe_event,
        error_category(error),
        type(error).__name__,
        location or "none",
    )
