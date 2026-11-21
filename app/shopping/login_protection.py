"""Best-effort login throttling for the single-process local Streamlit app."""

import hashlib
import threading
import time

MAX_FAILURES = 5
WINDOW_SECONDS = 300
_attempts: dict[str, tuple[int, float, float]] = {}
_lock = threading.Lock()


def _key(identifier: str) -> str:
    return hashlib.sha256(identifier.strip().lower().encode("utf-8")).hexdigest()


def login_allowed(identifier: str, now: float | None = None) -> bool:
    timestamp = time.monotonic() if now is None else now
    key = _key(identifier)
    with _lock:
        attempt = _attempts.get(key)
        if attempt is None:
            return True
        count, window_start, locked_until = attempt
        if timestamp < locked_until:
            return False
        if timestamp - window_start >= WINDOW_SECONDS:
            _attempts.pop(key, None)
        return True


def record_login_failure(identifier: str, now: float | None = None) -> None:
    timestamp = time.monotonic() if now is None else now
    key = _key(identifier)
    with _lock:
        previous = _attempts.get(key)
        if previous is None or timestamp - previous[1] >= WINDOW_SECONDS:
            count, window_start = 1, timestamp
        else:
            count, window_start = previous[0] + 1, previous[1]
        locked_until = timestamp + WINDOW_SECONDS if count >= MAX_FAILURES else 0.0
        _attempts[key] = (count, window_start, locked_until)
        while len(_attempts) > 4096:
            oldest = min(_attempts, key=lambda item: _attempts[item][1])
            _attempts.pop(oldest, None)


def clear_login_failures(identifier: str) -> None:
    with _lock:
        _attempts.pop(_key(identifier), None)
