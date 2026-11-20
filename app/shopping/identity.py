from collections.abc import MutableMapping
from typing import Any


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
    session.pop("authenticated_email", None)
    session.pop("authenticated_name", None)
    session.pop("authenticated_user_id", None)
    session["access_mode"] = "guest"


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
