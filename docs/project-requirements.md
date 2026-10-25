# Shopwise — AI Shopping Assistant
## Project Requirements Document

**Document status:** Current requirements and long-term product goals  
**Project type:** Streamlit e-commerce demonstration with an AI shopping assistant  
**Status terminology:** “Implemented” means the capability exists in the current project. Where appropriate, it also states what has or has not been verified. “Planned” describes a future goal and is not a claim about the current application.

## 1. Project overview

Shopwise is a Python application for browsing a local product catalog and asking natural-language shopping questions. Its current demonstration UI is built with Streamlit. The catalog is stored in SQLite. The AI path uses Google Gemini and a local Model Context Protocol (MCP) server that exposes a catalog search tool.

The long-term goal is a trustworthy shopping application that supports the full customer journey: account access, product discovery, comparisons and recommendations, saved products, reviews, discounts, checkout, orders, and delivery tracking. The current project is a local demonstration, not a production marketplace or payment system.

### Current implementation snapshot

- **Implemented:** Login and registration against a separate local account database; a guest browsing path; catalog search, filters, sorting, and grid/list layouts; session-only cart and wishlist; a clearly labelled demo checkout; and a Streamlit chat UI wired to the existing Gemini/MCP agent path.
- **Verified:** The documented automated test suite passed 39 tests on 2026-10-20. Tests exercise the catalog, cart, account flow, demo checkout, chat grounding, and application navigation. This does not establish production readiness.
- **Not verified:** A successful live Gemini response in the configured environment. A previous live attempt reached an MCP tool call but ended with an `ExceptionGroup`; do not treat the AI integration as live-verified.
- **Not implemented:** Persistent customer carts or wishlists, product review workflows, coupon application, real order creation, payment processing, order history, or delivery tracking.

## 2. Objectives

### Current demonstration objectives

1. Let a shopper enter the site as a guest or register and sign in to a local demo account.
2. Present products and catalog attributes from the existing `shopping.db`, without changing that database.
3. Support useful catalog discovery through search, filters, sorting, and multiple layouts.
4. Allow temporary cart and wishlist interactions without implying that they are persistent.
5. Provide a conversational catalog-search interface using the existing Gemini and MCP architecture, while communicating failures honestly.
6. Demonstrate checkout validation and a summary without charging a payment method or claiming that an order was placed.

### Long-term objectives

1. Support a secure, production-appropriate customer identity and account lifecycle.
2. Provide persistent customer shopping state and order ownership.
3. Support complete and reliable order placement, discounts, payment-provider integration, and order fulfilment.
4. Provide grounded, explainable AI assistance that is useful without inventing catalog facts.
5. Operate reliably, accessibly, and securely in a supported deployment environment.

## 3. Target users

### Current

- **Demo shoppers and evaluators:** Browse the real local catalog, use guest mode, explore filters and shopping controls, and try the assistant when Gemini credentials and connectivity are available.
- **Local demo operator/developer:** Runs the Streamlit app, maintains local configuration, and verifies changes using the project tests.

### Planned

- **Registered shoppers:** Manage an account, saved items, cart, addresses, orders, reviews, and support requests.
- **Store operators:** Maintain catalog, inventory, promotions, fulfilment, and customer support. No operator/admin interface is currently specified or implemented.

## 4. Functional requirements

“Implemented” requirements below describe the current local demonstration. “Planned” requirements are product goals requiring additional implementation and verification.

### 4.1 Registration, login, and guest access

**Implemented**

- The initial website view is a login screen, with registration and Continue as Guest paths.
- Registration validates a name, email format, and a minimum eight-character password; duplicate email addresses are rejected.
- Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes in a separate local `accounts.sqlite3` store, not as plaintext.
- Login verifies entered credentials and displays a generic invalid-credentials message on failure.
- A signed-in demo account can log out; guest access can return to the login screen.
- The account store is distinct from the catalog database’s `users` table. Existing catalog users do not thereby receive login credentials.

**Planned**

- Production-grade identity lifecycle, including password reset, verification, rate limiting, session controls, account recovery, and appropriate operational monitoring.
- An approved identity-to-customer data model before linking application accounts to catalog-database users, addresses, or orders.

### 4.2 Catalog, search, and filters

**Implemented**

- Catalog browsing reads product rows and category/brand names from the existing SQLite database.
- Search matches product name, description, SKU, brand, and category.
- Search can be combined with category, brand, minimum/maximum price, minimum rating, and in-stock-only filters.
- Price bounds and rating input are validated; invalid minimum/maximum ranges are rejected.
- Sort options include default/relevance ordering, price ascending/descending, highest rated, and name A–Z.
- The UI includes grid and list layouts, product details, available stock, ratings and review counts when present, and a clear-filters action.
- An empty result set is reported to the shopper.
- Product cards use an image-unavailable placeholder: no product image field or supplied product-image assets were found in the inspected project.

**Planned**

- Pagination or scalable catalog browsing if the catalog grows beyond the current local demonstration.
- Product imagery associated with the correct product and served from a controlled, validated source.
- Product comparison experiences beyond asking the assistant to search for catalog items.

### 4.3 Budget shopping and Gemini/MCP assistance

**Implemented in code; live service behavior is not verified**

- `app.agent.agent` orchestrates the configured Gemini model and tool calls; the runtime modules create the Gemini and MCP sessions.
- `app.mcp.mcp_server` exposes the `search_products` tool, which calls the existing product search implementation over SQLite.
- The agent supports catalog search filters including keywords, maximum price, minimum rating, stock requirement, and result limit.
- A budget request without an amount can prompt for the maximum budget. Catalog fields are formatted from tool-returned rows, and the Streamlit UI rejects ungrounded model product claims.
- The web app has a Python-backed Streamlit chat popover with in-session conversation state and user-facing error handling.

**Verification boundary**

- Automated tests use deterministic/fake Gemini client responses for agent behavior; one test starts the real local MCP server and checks database-backed search results.
- These tests do not prove that a live request to Gemini succeeds. A previous live attempt did not complete successfully, so external Gemini connectivity, credentials, and end-to-end live responses remain unverified.

**Planned**

- Repeatable live integration checks in an approved environment; robust retry, timeout, and provider-error policy; usage and cost controls; and broader intent evaluation.
- Further conversational workflows such as grounded product comparisons and task-specific advice, validated against actual tool results and user expectations.
- Do not expose private customer, account, cart, address, or order data to the model.

### 4.4 Cart and wishlist

**Implemented**

- Cart quantities use positive integers, are checked against current catalog stock, and are merged into one session line per product.
- Cart changes include quantity updates, removal, clearing, fresh catalog lookup, and subtotal/total recalculation from current catalog prices.
- Missing products, invalid quantities, and quantities exceeding current stock are handled as errors or unavailable items.
- The wishlist supports adding/removing products and is labelled as temporary session data.
- Cart and wishlist state is held in Streamlit session state for both guest and signed-in demo shoppers. It is not saved to the database.

**Planned**

- Persistent carts and wishlists tied to the authenticated shopper, with backend-enforced ownership.
- Explicit guest-cart migration/merge behavior on sign-in, including fresh price, existence, and stock validation.

### 4.5 Checkout, coupons, orders, and tracking

**Implemented**

- The Demo Checkout view rejects an empty cart and rechecks current products, stock, quantities, and price-derived totals.
- It displays an order-style summary and a clear confirmation that no order was placed or stored.
- It does not write order rows or charge a payment method.

**Planned**

- Coupon validation and application, including expiry, minimum order value, maximum discount, and server-side recalculation.
- Authenticated checkout with verified address and contact information; authoritative inventory reservation; transaction-safe order and order-item persistence; and clear recovery behavior for failures.
- Payment-provider integration only after separate requirements, legal/compliance review, provider selection, and secure implementation. Never store payment credentials in this application.
- Persistent order history, order status display, cancellations/returns where policy permits, and shipment tracking from a verified fulfilment source.
- No planned feature may report success until the corresponding persistent operation succeeds.

### 4.6 Product reviews and recommendations

**Implemented**

- Catalog display uses the existing aggregate rating and rating-count fields when present. This is display of stored catalog aggregates, not a review-writing feature.
- “Highest rated” sorting orders actual catalog rows by their stored rating fields.

**Planned**

- Authenticated review submission, editing/moderation policy, and verified-purchase rules; prevent duplicate or unauthorized reviews.
- Personalized recommendations based on explicitly approved data and transparent controls. Current rating-based sorting is not personalized recommendation behavior.

### 4.7 Deployment and operations

**Implemented**

- The application is runnable locally through Streamlit. The README provides local setup and run commands.

**Planned**

- Supported hosting environment, production secret management, HTTPS, access controls, persistent storage, backup/restore, observability, logging policy, availability targets, and deployment/release procedure.
- Operational controls for database backup and migration before any persistent feature modifies the existing catalog or customer/order schema.

## 5. Non-functional requirements

### Current expectations

- **Correctness:** Displayed catalog facts must come from SQLite or returned MCP results. Cart totals must use current catalog prices and validated integer quantities.
- **Safety:** Do not claim payment, persistent order creation, or successful live AI behavior without evidence.
- **Usability:** Clear guest/account entry points, readable states and feedback, compact catalog controls, and responsive Streamlit layouts.
- **Maintainability:** Keep the existing Python/Streamlit modules, agent path, MCP server, and catalog query layer understandable and testable.
- **Compatibility:** Use Python 3.10 or newer per the README and preserve the configured dependency compatibility, including `mcp[cli]==1.30.0`.
- **Data protection:** Keep `.env`, local databases, and credentials out of source control; read only catalog data for browsing.

### Planned production targets

- Define measurable availability, response-time, supported-browser/device, accessibility, backup/recovery, and data-retention targets before launch.
- Handle load, database contention, network/provider outages, and concurrent stock changes.
- Follow applicable privacy, consumer-protection, accessibility, security, and payment requirements for target markets.

## 6. Technical architecture

### Current stack and flow

```text
Shopper
  └─ Streamlit UI (app/ui/web_app.py)
       ├─ Local account auth (app/shopping/authentication.py → accounts.sqlite3)
       ├─ Session-only cart and wishlist (app/shopping/cart.py + Streamlit session state)
       ├─ Gemini agent (app/agent/agent.py)
       │    └─ MCP adapter and stdio client → app/mcp/mcp_server.py
       │         └─ search_products tool (app/tools/products_tool.py)
       │              └─ parameterized SQLite queries (app/db/products.py)
       └─ Catalog database connection (app/db/database.py → shopping.db, read-only)
```

### Planned architecture direction

- Preserve the current separation between UI, business rules, AI/MCP, and database access.
- Add authorization-aware service operations before exposing persistent carts, reviews, addresses, or orders.
- Keep authoritative pricing, coupon validation, stock checks, and order totals in backend/database operations rather than trusting UI or model output.
- A production database or service architecture must be selected based on documented scale, deployment, backup, and consistency requirements; no database migration is authorized by this document.

## 7. Database requirements

### Current database facts

- `shopping.db` is a local SQLite database. Catalog query code opens it using SQLite URI `mode=ro`.
- The inspected schema includes `products`, `categories`, and `brands`, with product fields for SKU, name, description, price, MRP, stock, average rating, and rating count.
- The schema also includes `users`, `addresses`, `cart_items`, `reviews`, `coupons`, `orders`, and `order_items`. Their presence does not mean the current UI implements or writes those workflows.
- Schema constraints include unique product SKU, category and brand names, nonnegative stock, positive product price, MRP not below price, review ratings from 1–5, unique review per product/user, positive cart/order-item quantities, and foreign keys connecting related rows.
- The `orders` schema requires a user and constrained status/payment-method values. The application currently does not create orders.
- Local demo account credentials are separate in `accounts.sqlite3`, which is created/initialized when the account code runs. It is not linked to `shopping.db` user IDs.
- The current application does not read private customer/order records for product browsing and does not use the database `cart_items`, `reviews`, `coupons`, `orders`, or `order_items` tables as active UI features.

### Requirements for future persistence

1. Preserve and back up the original database before any approved schema or record change.
2. Review and document existing relationships, constraints, indexes, and compatibility before migrations.
3. Use parameterized SQL, transactions, and rollback on failure.
4. Enforce user ownership and authorization in backend operations; never trust a client-supplied user ID.
5. Revalidate prices, stock, coupon rules, and totals server-side at order creation.
6. Define stock reservation and concurrency behavior to prevent overselling.
7. Keep credentials and sensitive data out of logs, generated AI prompts, test output, and documentation.
8. Require explicit approval for migrations or changes to the original database.

## 8. Security and privacy requirements

### Current safeguards

- Local account passwords are salted and hashed with PBKDF2-HMAC-SHA256; comparisons use a constant-time digest comparison.
- Catalog SQL values are parameterized; sort expressions are selected from an allowlist.
- Catalog connections are read-only.
- The app separates demo account records from the existing catalog/user database and does not treat existing catalog rows as authenticated accounts.
- The AI assistant is instructed to ground product claims in catalog results; the UI suppresses unsupported product recommendations.
- API credentials are configured outside source code in local environment configuration. Never include their values in documentation or output.

### Current risks and gaps

- The local account database and password flow are for demonstration, not a production identity service. Password reset, verification, login rate limiting, and production session controls are not implemented.
- Cart and wishlist data are session-only and are not authenticated persistent records.
- No production threat model, security review, penetration test, or deployment hardening evidence is documented here.
- Live Gemini error and credential handling was not proven by a successful external interaction.
- The existing SQLite schema contains customer/order-related tables; current catalog browsing must remain scoped to catalog data.

### Planned security requirements

- Threat-model authentication, authorization, account recovery, session lifecycle, CSRF/XSS, data access, AI prompt/tool boundaries, and deployment.
- Use an approved secrets manager in deployment; rotate and restrict credentials; never expose keys in browser code or logs.
- Add least-privilege access, ownership checks, safe output encoding, rate limits, auditability appropriate to privacy policy, and tested backup/recovery.
- Define privacy consent, collection minimization, retention/deletion, and customer-data access procedures before collecting real customer data.
- Never integrate real payments without a vetted provider and the necessary security, legal, and compliance review.

## 9. Testing requirements

### Current automated coverage

The documented `unittest` suite includes tests for agent/MCP behavior, budget filtering, catalog search and filtering, cart calculations and stock validation, demo authentication, chat-answer grounding, and Streamlit navigation/checkout behavior. On 2026-10-20, the documented command completed with **39 tests passing**.

These tests do not establish successful live Gemini connectivity, production security, production deployment behavior, real payment processing, persistent orders, or delivery tracking.

### Planned test coverage

- Unit tests for business rules and invalid inputs.
- SQLite integration tests using isolated fixtures or a safe test database, including transaction rollback, constraints, and concurrency.
- Authentication and authorization tests for ownership boundaries and session expiry.
- UI integration and accessibility checks across desktop and mobile sizes.
- Gemini/MCP contract and error-path tests, plus controlled live smoke tests when credentials and network access are explicitly available.
- Security testing, dependency review, recovery tests, and load/performance testing before production deployment.

## 10. Acceptance criteria

### Current demonstration acceptance

- A first-time visitor sees login and can choose guest access; registration and login use verified credentials and never store plaintext passwords.
- Catalog results and filters use real product rows; combined filters, bounds, sort ordering, and no-result behavior are tested.
- Cart actions validate quantities against current stock and recalculate totals from current product data.
- Wishlist and cart behavior is clearly identified as session-only.
- Demo checkout validates a non-empty cart and current catalog state, then explicitly confirms that no order was placed or stored.
- Chat product facts are only shown when grounded in returned catalog results; errors do not masquerade as successful recommendations.
- Automated tests pass using the documented suite.

### Future production acceptance

- A shopper can securely register/sign in, recover access, and access only their own saved state and order records.
- Search, filters, and recommendations return current, explainable catalog facts.
- Reviews, coupons, checkout, stock reservation, orders, history, and tracking each satisfy separately defined authorization, correctness, audit, and failure-recovery tests.
- Payment is processed only through an approved provider; order success is shown only after an authoritative successful transaction.
- Deployment meets agreed accessibility, security, privacy, performance, backup, and operational objectives.

## 11. Constraints and assumptions

- Existing implementation uses Python, Streamlit, and SQLite, with Google Gemini and MCP for AI-assisted catalog search.
- `requirements.txt` pins `mcp[cli]==1.30.0`; this version must not be upgraded as an incidental change.
- The project README specifies Python 3.10 or newer and provides local Streamlit run and test commands.
- `shopping.db` is an existing source of catalog data and must not be recreated, seeded, overwritten, or migrated without separate review and approval.
- `.env` and local databases are private local configuration/data and must remain excluded from documentation content and source control.
- The current application is a demonstration: no real payment, persistent order creation, production deployment, or production identity management is claimed.
- Gemini use requires a configured key and network access. Availability and live behavior are environment-dependent.
- No product images were identified in the current catalog schema or supplied assets.

## 12. Future enhancements and suggested sequence

1. Define identity and customer-account ownership; decide whether to integrate with existing `users` or use a separately designed identity store.
2. Design safe persistent cart and wishlist services, including guest merge semantics.
3. Define review eligibility, moderation, and update rules.
4. Specify coupon validation and order-total calculation rules.
5. Design order creation, stock reservation, address handling, and transaction/error semantics; approve a backed-up migration if required.
6. Select and integrate a payment provider only after dedicated security/compliance approval.
7. Add order history, cancellation/returns policy, fulfilment status, and verified tracking integration.
8. Expand AI-assisted comparisons/recommendations with grounding, evaluation, and privacy boundaries.
9. Define production deployment, monitoring, backup/restore, accessibility, privacy, and support requirements.
