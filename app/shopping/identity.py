from collections.abc import MutableMapping
from typing import Any
import logging


def clear_chat_session(session: MutableMapping[str, Any]) -> None:
    for key, value in (
        ("chat_messages", []),
        ("agent_history", []),
        ("chat_pending_reply", None),
        ("chat_processing", False),
        ("chat_open", False),
    ):
        session[key] = value


def clear_user_session_data(session: MutableMapping[str, Any]) -> None:
    session["cart"] = {}
    session["wishlist"] = set()
    session.pop("_cart_synced_user_id", None)
    clear_chat_session(session)


def prepare_login_session(session: MutableMapping[str, Any]) -> None:
    was_authenticated = session.get("access_mode") == "authenticated"
    _clear_identity(session)
    session.pop("access_mode", None)
    clear_chat_session(session)
    if was_authenticated:
        clear_user_session_data(session)


def enter_guest_session(session: MutableMapping[str, Any]) -> None:
    was_authenticated = session.get("access_mode") == "authenticated"
    _clear_identity(session)
    session["access_mode"] = "guest"
    clear_chat_session(session)
    if was_authenticated:
        clear_user_session_data(session)


def _clear_identity(session: MutableMapping[str, Any]) -> None:
    session.pop("authenticated_email", None)
    session.pop("authenticated_name", None)
    session.pop("authenticated_user_id", None)


def require_authenticated_user(
    session: MutableMapping[str, Any],
) -> str:
    """Return the canonical shopping user ID or reject guest/invalid state."""
    if session.get("access_mode") != "authenticated":
        raise PermissionError("Authentication is required.")

    user_id = session.get("authenticated_user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise PermissionError("A canonical shopping identity is required.")
    return user_id


def clear_authenticated_session(
    session: MutableMapping[str, Any],
) -> None:
    """Remove all authenticated identity values from session state."""
    _clear_identity(session)
    session["access_mode"] = "guest"
    clear_user_session_data(session)
    logging.getLogger("app.authentication").info("event=logout")


def ensure_resource_owner(
    resource_user_id: str,
    authenticated_user_id: str,
) -> None:
    """Reject access to a resource owned by another user."""
    if (
        not isinstance(resource_user_id, str)
        or not isinstance(authenticated_user_id, str)
        or resource_user_id != authenticated_user_id
    ):
        raise PermissionError("You do not have permission to access this resource.")
