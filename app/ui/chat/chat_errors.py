import asyncio
import logging
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def _chat_error_message(error: Exception) -> str:
    load_dotenv(PROJECT_ROOT / ".env")

    if not os.getenv("GEMINI_API_KEY"):
        return (
            "The AI assistant is not configured yet. Add GEMINI_API_KEY to "
            "the project-root .env file, then restart Shopwise."
        )

    category, _status_code = _classify_chat_error(error)

    if category == "timeout":
        return "The AI request timed out. Please try again."

    if category == "connection":
        return "Shopwise couldn't connect to Gemini. Check your connection and try again."

    if category == "authentication":
        return "Gemini rejected the configured credentials. Check the API key and its access."

    if category == "rate_limit":
        return "Gemini is receiving too many requests right now. Please wait a moment and try again."

    if category == "model_or_request":
        return (
            "Gemini rejected this request or model configuration. Check the selected "
            "GEMINI_MODEL and try again."
        )

    if category == "api_service":
        return "Gemini is temporarily unavailable. Please try again shortly."

    return (
        "The AI assistant couldn't complete this request. Please try again. "
        "If the problem continues, check the terminal diagnostic."
    )

def _exception_chain(error: BaseException) -> list[BaseException]:
    found: list[BaseException] = []
    pending = [error]
    visited: set[int] = set()

    while pending:
        current = pending.pop()

        if id(current) in visited:
            continue

        visited.add(id(current))
        found.append(current)

        children = getattr(current, "exceptions", None)
        if isinstance(children, tuple):
            pending.extend(
                child for child in children if isinstance(child, BaseException)
            )

        cause = current.__cause__ or current.__context__
        if cause is not None:
            pending.append(cause)

    return found

def _classify_chat_error(error: BaseException) -> tuple[str, int | None]:
    chain = _exception_chain(error)

    if any(
        isinstance(item, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException))
        or any(
            cls.__name__ == "APITimeoutError"
            for cls in type(item).__mro__
        )
        for item in chain
    ):
        return "timeout", None

    if any(
        isinstance(item, (httpx.NetworkError, ConnectionError))
        or any(
            cls.__name__ == "APIConnectionError"
            for cls in type(item).__mro__
        )
        for item in chain
    ):
        return "connection", None

    api_error_names = {
        "APIError",
        "APIStatusError",
        "AuthenticationError",
        "PermissionDeniedError",
        "RateLimitError",
        "NotFoundError",
        "BadRequestError",
        "InternalServerError",
    }

    api_error = next(
        (
            item
            for item in chain
            if any(cls.__name__ in api_error_names for cls in type(item).__mro__)
        ),
        None,
    )

    status = None

    if api_error is not None:
        status = getattr(api_error, "status_code", None)
        if status is None:
            status = getattr(api_error, "code", None)

    if status is None:
        status = next(
            (
                getattr(item, "status_code", getattr(item, "code", None))
                for item in chain
                if isinstance(
                    getattr(item, "status_code", getattr(item, "code", None)),
                    int,
                )
            ),
            None,
        )

    status = status if isinstance(status, int) else None

    if status in (401, 403):
        return "authentication", status

    if status == 429:
        return "rate_limit", status

    if status is not None and 400 <= status < 500:
        return "model_or_request", status

    if api_error is not None or (status is not None and status >= 500):
        return "api_service", status

    return "unknown", status

def _log_chat_exception(error: Exception) -> None:
    category, status = _classify_chat_error(error)
    chain_types = ",".join(type(item).__name__ for item in _exception_chain(error))

    logging.getLogger(__name__).error(
        "Shopwise Gemini request failed: category=%s status=%s exception_types=%s",
        category,
        status if status is not None else "none",
        chain_types,
    )
