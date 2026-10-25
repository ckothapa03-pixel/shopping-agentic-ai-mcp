# Shopwise — Project Progress

**Status reviewed:** 2026-10-20  
**Evidence basis:** Current project files, test source, SQLite schema definitions (schema only), and one documented run of the existing automated test command. No database records or secrets are included here.

## 1. Project architecture and existing modules

The project is a Python/Streamlit application with a local SQLite catalog and an AI shopping path. The current module flow is:

```text
app/ui/web_app.py
  ├─ app/ui/auth.py → app/shopping/authentication.py → accounts.sqlite3
  ├─ app/ui/catalog.py → app/ui/catalog_data.py → app/db/products.py
  ├─ app/ui/cart_pages.py → app/shopping/cart.py
  └─ app/ui/chat/chat.py → app/agent/chat_runtime.py → app/agent/agent.py
                                         └─ app/mcp/mcp_tools.py → app/mcp/mcp_server.py
                                                                    └─ app/tools/products_tool.py
                                                                         └─ app/db/products.py
                                                                              └─ app/db/database.py → shopping.db
```

| Module or file | Observed responsibility |
| --- | --- |
| `app/ui/web_app.py` | Streamlit entry point that routes to the UI modules. |
| `app/shopping/authentication.py` | Uses the separate account database; validates registration and verifies salted password hashes. |
| `app/shopping/cart.py` | Cart quantity and stock validation, recalculation, and non-empty demo-checkout validation. |
| `app/agent/agent.py` | Gemini response orchestration, MCP tool handling, budget clarification, and formatting returned product rows. |
| `app/agent/chat_runtime.py` | Sets up Gemini and MCP for Streamlit chat. |
| `app/agent/agent_cli.py` | Provides the terminal chat loop. |
| `app/mcp/mcp_server.py` | FastMCP server exposing `search_products`. |
| `app/tools/products_tool.py` | Application interface and result-limit validation for catalog searches. |
| `app/db/products.py` | Parameterized catalog search, facets, allowlisted sorting, and fresh lookup by product IDs. |
| `app/db/database.py` | Resolves the project-local `shopping.db` and opens it with SQLite `mode=ro`. |
| `main.py` | Starts the MCP server. |
| `.streamlit/config.toml` | Streamlit theme configuration. |
| `requirements.txt` | Declares Google GenAI, dotenv, Streamlit, and `mcp[cli]==1.30.0`. |
| `README.md`, `LLM_INTEGRATION.md` | Local setup, run instructions, architecture description, and known demo limitations. |

The database schema includes catalog tables and tables for users, addresses, carts, reviews, coupons, orders, and order items. The current UI actively reads the catalog tables only. Schema presence is not evidence that those other workflows are implemented.

## 2. Implemented features

### Account entry

- Login is the initial view; guests can continue without creating an account.
- Registration validates name, email format, password length, and confirmation. Duplicate email is rejected.
- Password hashes use salted PBKDF2-HMAC-SHA256 in a separate `accounts.sqlite3` database.
- Invalid credentials are handled with a generic message. A signed-in demo account can log out.
- **Boundary:** These local demo accounts are not linked to the `users` records in `shopping.db`.

### Catalog

- Product catalog rows are queried from the existing SQLite database using read-only connections.
- Search includes product name, description, SKU, brand, and category.
- Category, brand, minimum/maximum price, minimum rating, and stock filters combine in the query.
- Invalid price bounds and ratings are rejected; sorting uses a fixed allowlist.
- UI controls include category navigation, filter clearing, product count, grid/list modes, product details, prices, stock, and stored ratings/review counts.
- Empty results are displayed. Product cards use an unavailable-image placeholder because no image column or supplied product assets were identified.

### Shopping interactions

- Cart add, update, removal, clear, and total calculation are implemented in testable Python functions and the Streamlit UI.
- Quantity validation uses current stock and positive integer quantities. Cart values and checkout totals are rechecked using fresh catalog rows.
- A wishlist supports adding and removing product IDs.
- Both cart and wishlist are held only in Streamlit session state, including for signed-in demo accounts.
- Demo checkout validates the cart and displays a confirmation explicitly stating that no order was placed or stored. It does not write an order or take payment.

### AI and MCP

- The chatbot popover is implemented with Streamlit controls connected to Python backend logic.
- The UI invokes the existing agent path; the agent starts the local MCP server over stdio and supplies the `search_products` tool to Gemini.
- The search tool uses SQLite-backed product results. Budget clarification and response grounding have automated test coverage.
- On a prior live integration attempt recorded during the preceding project work, execution reached an MCP tool call but failed with an `ExceptionGroup`. A successful live Gemini response has **not** been verified.

## 3. Features that need additional testing

- **Live Gemini/MCP from the running website:** The code path is connected and automated behavior is covered with deterministic client fixtures, but external credentials/network behavior did not complete successfully in the previous live attempt. Retest only in an environment with valid credentials and network access; do not print the key.
- **Chat widget visual behavior:** Automated tests cover answer grounding, not all browser interactions, responsive layouts, keyboard use, or persistence of chat history after app reruns.
- **Responsive interface and accessibility:** The UI includes responsive CSS/layout handling, but no complete screen-reader, keyboard, browser matrix, or accessibility audit was verified in this task.
- **SQLite failure and contention cases:** Basic query behavior is exercised, but production concurrency, large-catalog performance, locking, and disaster recovery are not established.
- **Authentication hardening:** Tests cover registration, hash storage, and credential verification; they do not establish rate limiting, password recovery, identity verification, or production session security.
- **Cart behavior across browser sessions:** Current tests establish in-session behavior only; persistence is intentionally not implemented.
- **External deployment:** No hosted deployment, production configuration, or deployment smoke test was verified.

## 4. Incomplete or planned features

- Persistent user-owned carts and wishlists; guest-to-account cart merge.
- Linking local demo accounts safely to customer/user identity in the catalog/order database.
- Product review submission, editing, moderation, and verified-purchase handling. Existing rating aggregates are displayed, but the UI does not write reviews.
- Coupon lookup and validation. A `coupons` table exists in the schema, but it is not part of current shopping or checkout behavior.
- Real checkout, transactional order/order-item creation, inventory reservation, and address selection.
- Payment processing. No payment provider is integrated; the demo checkout does not charge or persist an order.
- Order history, cancellation/returns workflow, and delivery tracking.
- Personalized product recommendations. Current “highest rated” sorting is a catalog sort, not a personalized recommendation system.
- Product images. The current project uses a neutral placeholder.
- Production deployment, monitoring, backups, operational support, and security hardening.

## 5. Known limitations and risks

1. **Demo account separation:** Registration uses a local `accounts.sqlite3` store. Existing `shopping.db` user rows have no password credentials and are not used to authenticate these accounts.
2. **Temporary shopping state:** Cart, wishlist, and chat state are not persistent account data and may disappear when a session ends.
3. **No persistent checkout:** The app recalculates a demo summary but does not create order rows or take payment. Its confirmation explicitly says so.
4. **Dormant database schema:** `users`, `addresses`, `cart_items`, `reviews`, `coupons`, `orders`, and `order_items` exist in `shopping.db`, but their existence does not mean current application features use them. No schema migration was performed.
5. **External AI uncertainty:** Gemini requires a valid local key and network connectivity. A live response was not successfully verified; avoid presenting the integration as live-confirmed.
6. **No production authentication controls:** The local registration flow has no verified password-reset, email-verification, or login-rate-limiting flow and is not production identity management.
7. **No product images:** No valid image URL or image asset was found in the project/schema inspected.
8. **Operational assurance:** No production threat model, formal security review, load test, backup/restore test, or deployment verification is established by the available evidence.

## 6. Tests and their actual results

### Test files inspected

| Test file | Coverage indicated by its tests |
| --- | --- |
| `tests/test_agent.py` | Gemini-agent orchestration with test doubles, MCP tool calls, budget clarification, malformed tool arguments, errors, and database-backed MCP budget flow. |
| `tests/test_user_story_7.py` | Product search, budget, rating/stock filters, result limits, and product fields from the real local catalog. |
| `tests/test_catalog.py` | Search, combined filters, price boundaries, sorting, validation, catalog facets, fresh product lookup, and no-result behavior. |
| `tests/test_cart.py` | Cart add/update/remove, totals, invalid quantities, stock overflow, missing products, and checkout validation. |
| `tests/test_authentication.py` | Registration, password-hash storage, credential verification, duplicate accounts, and invalid registration. |
| `tests/test_web_app.py` | Chat answer grounding, budget clarification, and refusal to present unsupported product claims. |
| `tests/test_web_navigation.py` | Login-first view, guest and account flows, logout, wishlist state, demo checkout, search, and clearing filters through Streamlit `AppTest`. |
| `examples/demo_product_search.py` | A demonstration script that prints catalog results; it is not an automated unittest module and was not run for this status review. |

### Run performed for this progress report

From the project root, with the existing parent virtual environment:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m unittest discover -s tests -v
```

**Result:** 39 tests ran in 29.388 seconds; **OK (39 passed, 0 failures, 0 errors)** on 2026-10-20. The output included expected Streamlit bare-mode warnings and MCP tool request logs.

The suite uses deterministic Gemini test doubles. The MCP budget-flow test starts the local MCP server and queries the real catalog, but it does not make a live Gemini request. The successful test run therefore verifies the covered local paths, not external Gemini connectivity or production behavior.

## 7. Recommended next development steps

1. **Set scope and trust boundaries:** Confirm whether the next milestone remains a local demonstration or becomes a production-bound application. Define account ownership, data privacy, order lifecycle, and deployment expectations first.
2. **Decide identity architecture:** Design how demo identities relate to the existing `users` table or a future identity provider. Do not silently change the existing database or assume an existing user is authenticated.
3. **Add persistent cart and wishlist safely:** Implement backend ownership checks, persistence, guest merge rules, and current-stock validation with isolated tests.
4. **Specify order creation before coding:** Define address ownership, coupon rules, authoritative totals, stock reservation, transaction/rollback behavior, and order-state transitions. Review and back up the database, then seek approval before any required migration.
5. **Build customer features in stages:** Add review permissions/moderation, coupons, order history, and tracking only after their data ownership and failure behavior are specified.
6. **Validate AI behavior:** Diagnose the prior live failure without exposing credentials, then run a controlled live smoke test if the user has a valid key and network access. Add bounded timeouts/error tests and verify that results remain catalog-grounded.
7. **Improve quality evidence:** Add focused responsive/accessibility checks, database transaction/concurrency cases, and dependency/security review.
8. **Plan deployment:** Select hosting and secret management, define HTTPS, persistence, monitoring, backups, restore drills, and privacy requirements before describing the app as production-ready.
