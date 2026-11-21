import logging
import os

DEFAULT_GEMINI_TIMEOUT_SECONDS = 90
MIN_GEMINI_TIMEOUT_SECONDS = 5
MAX_GEMINI_TIMEOUT_SECONDS = 300


def gemini_timeout_seconds() -> int:
    raw_timeout = os.getenv("GEMINI_TIMEOUT_SECONDS")
    if raw_timeout is None:
        return DEFAULT_GEMINI_TIMEOUT_SECONDS
    try:
        timeout = int(raw_timeout)
    except (TypeError, ValueError):
        logging.getLogger(__name__).warning(
            "Ignoring invalid GEMINI_TIMEOUT_SECONDS; using the default."
        )
        return DEFAULT_GEMINI_TIMEOUT_SECONDS
    if not MIN_GEMINI_TIMEOUT_SECONDS <= timeout <= MAX_GEMINI_TIMEOUT_SECONDS:
        logging.getLogger(__name__).warning(
            "GEMINI_TIMEOUT_SECONDS must be between %s and %s; using the default.",
            MIN_GEMINI_TIMEOUT_SECONDS,
            MAX_GEMINI_TIMEOUT_SECONDS,
        )
        return DEFAULT_GEMINI_TIMEOUT_SECONDS
    return timeout
