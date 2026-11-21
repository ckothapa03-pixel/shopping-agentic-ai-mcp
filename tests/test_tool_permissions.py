import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.agent.agent import respond
from app.agent.tool_permissions import (
    AUTONOMOUS_TOOL_NAMES,
    TOOL_RISK,
    ToolPermissionDenied,
    ToolRisk,
    filter_autonomous_tools,
)
from app.mcp.mcp_tools import call_mcp_tool
from app.agent.chat_runtime import _respond_with_mcp
from app.shopping.confirmation import (
    confirmation_matches,
    consume_confirmation,
    request_confirmation,
)


def _tool(name: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        description=f"{name} description",
        inputSchema={"type": "object", "properties": {}},
    )


class ToolPermissionTests(unittest.IsolatedAsyncioTestCase):
    def test_policy_classifies_all_registered_tool_names(self) -> None:
        self.assertEqual(len(TOOL_RISK), 21)
        self.assertEqual(AUTONOMOUS_TOOL_NAMES, {
            "search_products",
            "get_product_details",
            "get_categories",
            "get_brands",
            "compare_products",
            "get_similar_products",
            "search_policies",
        })
        self.assertEqual(TOOL_RISK["view_cart"], ToolRisk.USER_READ)
        self.assertEqual(TOOL_RISK["clear_cart"], ToolRisk.MUTATION)
        self.assertEqual(TOOL_RISK["create_checkout_order"], ToolRisk.CONSEQUENTIAL)

    def test_gemini_gets_only_known_safe_read_tools(self) -> None:
        discovered = [_tool(name) for name in TOOL_RISK]
        discovered.extend([_tool("future_unknown_tool"), _tool("cancel_order")])

        tools = filter_autonomous_tools(discovered)

        self.assertEqual({tool["name"] for tool in tools}, AUTONOMOUS_TOOL_NAMES)
        self.assertEqual(len(tools), len(AUTONOMOUS_TOOL_NAMES))

    async def test_execution_boundary_denies_private_mutating_and_unknown_tools(self) -> None:
        session = SimpleNamespace(call_tool=AsyncMock())

        for name in ("view_cart", "set_wishlist", "cancel_order", "future_unknown_tool"):
            with self.subTest(name=name), self.assertRaises(ToolPermissionDenied):
                await call_mcp_tool(session, name, {"user_id": "USR-OTHER"})

        session.call_tool.assert_not_awaited()

    async def test_model_generated_call_to_sensitive_tool_is_rejected(self) -> None:
        discovered = [_tool(name) for name in TOOL_RISK]
        session = SimpleNamespace(
            list_tools=AsyncMock(return_value=SimpleNamespace(tools=discovered)),
            call_tool=AsyncMock(),
        )
        unauthorized_call = SimpleNamespace(
            type="function_call",
            id="call-sensitive",
            name="create_checkout_order",
            arguments={
                "address_id": 4,
                "user_id": "USR-OTHER",
                "confirmation": True,
            },
            model_dump=lambda **_: {
                "type": "function_call",
                "id": "call-sensitive",
                "name": "create_checkout_order",
                "arguments": {
                    "address_id": 4,
                    "user_id": "USR-OTHER",
                    "confirmation": True,
                },
            },
        )
        client = SimpleNamespace(
            interactions=SimpleNamespace(
                create=AsyncMock(
                    return_value=SimpleNamespace(
                        steps=[unauthorized_call], output_text="The order is placed."
                    )
                )
            )
        )

        answer = await respond(session, client, "Place this order", "test-model")

        self.assertIn("not available to the AI assistant", answer)
        session.call_tool.assert_not_awaited()
        first_tools = client.interactions.create.await_args_list[0].kwargs["tools"]
        self.assertEqual({tool["name"] for tool in first_tools}, AUTONOMOUS_TOOL_NAMES)
        client.interactions.create.assert_awaited_once()


class ConfirmationTests(unittest.TestCase):
    def test_confirmation_is_bound_to_action_and_parameters(self) -> None:
        state = {}
        request_confirmation(
            state, "pending", "cancel_order", "USR-A", {"order_id": 10}
        )

        self.assertFalse(
            confirmation_matches(
                state, "pending", "cancel_order", "USR-A", {"order_id": 11}
            )
        )
        self.assertNotIn("pending", state)

    def test_confirmation_cannot_authorize_another_action_or_user(self) -> None:
        for operation, user_id in (("create_checkout_order", "USR-A"), ("cancel_order", "USR-B")):
            state = {}
            request_confirmation(
                state, "pending", "cancel_order", "USR-A", {"order_id": 10}
            )
            self.assertFalse(
                consume_confirmation(
                    state, "pending", operation, user_id, {"order_id": 10}
                )
            )
            self.assertNotIn("pending", state)

    def test_confirmation_is_one_use(self) -> None:
        state = {}
        request_confirmation(
            state, "pending", "cancel_order", "USR-A", {"order_id": 10}
        )
        parameters = {"order_id": 10}

        self.assertTrue(
            consume_confirmation(state, "pending", "cancel_order", "USR-A", parameters)
        )
        self.assertFalse(
            consume_confirmation(state, "pending", "cancel_order", "USR-A", parameters)
        )


class McpToolConfirmationTests(unittest.TestCase):
    def test_all_mcp_mutations_and_order_actions_require_confirmation(self) -> None:
        from app.mcp import mcp_server

        operations = (
            (mcp_server.add_to_cart, (1, 1)),
            (mcp_server.update_cart_quantity, (1, 1)),
            (mcp_server.remove_from_cart, (1,)),
            (mcp_server.clear_cart, ()),
            (mcp_server.set_wishlist, (1, True)),
            (mcp_server.create_checkout_order, (1,)),
            (mcp_server.cancel_order, (1,)),
        )
        with (
            patch.object(mcp_server, "_session_user_id", "USR-A"),
            patch.object(mcp_server, "set_cart_quantity") as write_cart,
            patch.object(mcp_server, "remove_cart_item") as remove_cart,
            patch.object(mcp_server, "clear_cart_from_db") as clear_cart,
            patch.object(mcp_server, "set_wishlist_from_db") as write_wishlist,
            patch.object(mcp_server, "create_order") as place_order,
        ):
            for operation, arguments in operations:
                with self.subTest(operation=operation.__name__):
                    with self.assertRaises(ToolPermissionDenied):
                        operation(*arguments)
        write_cart.assert_not_called()
        remove_cart.assert_not_called()
        clear_cart.assert_not_called()
        write_wishlist.assert_not_called()
        place_order.assert_not_called()

    def test_guest_cannot_access_private_mcp_tools(self) -> None:
        from app.mcp import mcp_server

        with patch.object(mcp_server, "_session_user_id", None):
            with self.assertRaises(PermissionError):
                mcp_server.view_cart()


class _AsyncContext:
    def __init__(self, value=None) -> None:
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return None


class IdentityContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_authenticated_identity_is_supplied_by_runtime_not_tool_arguments(self) -> None:
        from app.agent import chat_runtime

        with (
            patch.object(chat_runtime, "stdio_client", return_value=_AsyncContext((None, None))) as child,
            patch.object(
                chat_runtime,
                "ClientSession",
                return_value=_AsyncContext(SimpleNamespace(initialize=AsyncMock())),
            ),
            patch.object(chat_runtime, "_respond_with_session", new=AsyncMock(return_value="ok")),
        ):
            result = await _respond_with_mcp(
                client=object(),
                user_message="Show my profile",
                model="test-model",
                conversation_history=[],
                product_results=None,
                product_search_performed=None,
                product_search_loader=None,
                on_text_delta=None,
                on_stage=None,
                user_id="USR-AUTHENTICATED",
            )

        self.assertEqual(result, "ok")
        parameters = child.call_args.args[0]
        self.assertEqual(parameters.env["SHOPWISE_USER_ID"], "USR-AUTHENTICATED")


if __name__ == "__main__":
    unittest.main()
