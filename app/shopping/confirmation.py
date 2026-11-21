"""One-use, server-side confirmation records bound to an exact action."""

import hashlib
import hmac
import json
import secrets
from collections.abc import MutableMapping
from typing import Any


def _fingerprint(operation: str, user_id: str, parameters: Any) -> str:
    canonical = json.dumps(
        [operation, user_id, parameters],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def request_confirmation(
    state: MutableMapping[str, Any],
    key: str,
    operation: str,
    user_id: str,
    parameters: Any,
) -> None:
    """Record a pending action in server-side session state, never model input."""
    state[key] = {
        "nonce": secrets.token_urlsafe(32),
        "fingerprint": _fingerprint(operation, user_id, parameters),
    }


def confirmation_matches(
    state: MutableMapping[str, Any],
    key: str,
    operation: str,
    user_id: str,
    parameters: Any,
) -> bool:
    """Check current UI values; invalidate stale approval immediately."""
    pending = state.get(key)
    if not isinstance(pending, dict):
        return False
    expected = _fingerprint(operation, user_id, parameters)
    if not hmac.compare_digest(str(pending.get("fingerprint", "")), expected):
        state.pop(key, None)
        return False
    return True


def consume_confirmation(
    state: MutableMapping[str, Any],
    key: str,
    operation: str,
    user_id: str,
    parameters: Any,
) -> bool:
    """Consume a confirmation exactly once and only for its original action."""
    pending = state.pop(key, None)
    if not isinstance(pending, dict) or not pending.get("nonce"):
        return False
    expected = _fingerprint(operation, user_id, parameters)
    return hmac.compare_digest(str(pending.get("fingerprint", "")), expected)
