"""Central policy for tools the language model may invoke autonomously."""

from enum import Enum
import logging
from typing import Any


class ToolRisk(str, Enum):
    SAFE_READ = "safe_read"
    USER_READ = "user_read"
    MUTATION = "mutation"
    CONSEQUENTIAL = "consequential"


TOOL_RISK: dict[str, ToolRisk] = {
    "search_products": ToolRisk.SAFE_READ,
    "get_product_details": ToolRisk.SAFE_READ,
    "get_categories": ToolRisk.SAFE_READ,
    "get_brands": ToolRisk.SAFE_READ,
    "compare_products": ToolRisk.SAFE_READ,
    "get_similar_products": ToolRisk.SAFE_READ,
    "search_policies": ToolRisk.SAFE_READ,
    "view_cart": ToolRisk.USER_READ,
    "view_wishlist": ToolRisk.USER_READ,
    "get_addresses": ToolRisk.USER_READ,
    "get_orders": ToolRisk.USER_READ,
    "get_order_details": ToolRisk.USER_READ,
    "track_order": ToolRisk.USER_READ,
    "get_user_profile": ToolRisk.USER_READ,
    "add_to_cart": ToolRisk.MUTATION,
    "update_cart_quantity": ToolRisk.MUTATION,
    "remove_from_cart": ToolRisk.MUTATION,
    "clear_cart": ToolRisk.MUTATION,
    "set_wishlist": ToolRisk.MUTATION,
    "create_checkout_order": ToolRisk.CONSEQUENTIAL,
    "cancel_order": ToolRisk.CONSEQUENTIAL,
}

AUTONOMOUS_TOOL_NAMES = frozenset(
    name for name, risk in TOOL_RISK.items() if risk is ToolRisk.SAFE_READ
)
_logger = logging.getLogger(__name__)


class ToolPermissionDenied(PermissionError):
    """An MCP tool was not approved for autonomous model execution."""


def filter_autonomous_tools(discovered_tools: list[Any]) -> list[dict[str, Any]]:
    """Return only known safe-read tool schemas; unknown tools default to deny."""
    approved = []
    seen: set[str] = set()
    for tool in discovered_tools:
        name = getattr(tool, "name", None)
        if name not in AUTONOMOUS_TOOL_NAMES or name in seen:
            continue
        seen.add(name)
        approved.append(
            {
                "type": "function",
                "name": name,
                "description": getattr(tool, "description", None) or "",
                "parameters": getattr(tool, "inputSchema", {}),
            }
        )
    return approved


def require_autonomous_permission(tool_name: str) -> None:
    """Enforce the AI tool policy immediately before an MCP invocation."""
    if tool_name in AUTONOMOUS_TOOL_NAMES:
        return
    risk = TOOL_RISK.get(tool_name, "unknown")
    _logger.warning(
        "Blocked autonomous MCP tool invocation: tool=%s risk=%s",
        tool_name if tool_name in TOOL_RISK else "unknown",
        risk,
    )
    raise ToolPermissionDenied(
        "This operation is not available to the AI assistant. Use the "
        "corresponding Shopwise control to review and confirm it."
    )


def require_explicit_confirmation(tool_name: str) -> None:
    """Require trusted host context for mutating or consequential MCP tools.

    MCP has no trusted user-confirmation channel, so model output and MCP tool
    arguments can never satisfy this check. Current Streamlit flows execute
    these actions through their own confirmed UI path instead.
    """
    risk = TOOL_RISK.get(tool_name)
    if risk not in {ToolRisk.MUTATION, ToolRisk.CONSEQUENTIAL}:
        raise ToolPermissionDenied("Tool is not a confirmable operation.")
    _logger.warning(
        "Blocked unconfirmed MCP operation: tool=%s risk=%s",
        tool_name,
        risk,
    )
    raise ToolPermissionDenied(
        "This operation requires confirmation in the Shopwise application."
    )
