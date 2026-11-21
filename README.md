# Shopwise Agentic AI Shopping

Shopwise is a Streamlit shopping application backed by existing SQLite databases. Its optional Gemini shopping assistant uses a local FastMCP server for catalog tools.

## Architecture and features

- `app/ui/` contains the Streamlit pages and chat interface.
- `app/shopping/` contains authentication, shopping rules, checkout confirmation, and money handling.
- `app/db/` contains SQLite connections, schema validation, and repositories.
- `app/agent/` connects Gemini to the permission-filtered MCP tools.
- `app/mcp/` exposes the tools through FastMCP over stdio.
- `app/tools/` contains the catalog search adapter; `app/rag/` contains optional local document retrieval.

The catalog, cart, wishlist, addresses, and orders use the existing database layer. Guest cart and wishlist state is session-only. Authenticated accounts are linked to active shopper records through `identity_mappings`; the app does not create missing databases or schemas. Checkout revalidates the cart, coupon, prices, and stock before creating an order. Payment is limited to the application's configured COD flow; there is no external payment processor.

Gemini receives only the approved autonomous read-only catalog tools. User-specific, mutating, and consequential MCP operations are protected by application authorization and confirmation policy.

## Requirements and installation

Use Python 3.11 or newer. Create a virtual environment from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The direct dependencies are pinned in `requirements.txt`, including the MCP version. Transitive packages are resolved by pip; the repository does not currently maintain a platform-specific full lock file.

## Databases

The application requires existing `shopping.db` and `accounts.sqlite3` files with the tables and columns checked by the read-only startup validator. Supply databases provisioned for the application; startup and tests do not create, migrate, or seed them. Keep private database files outside source control. `.gitignore` excludes both database names, `.env` files, virtual environments, Python caches, and Streamlit secrets.

Startup verifies the required tables and columns without exposing records. To run the same read-only readiness validation from the project root:

```powershell
python -c "from app.db.schema import validate_shopping_schema, validate_account_schema; validate_shopping_schema(); validate_account_schema(); print('Database readiness checks passed')"
```

For a non-default shopping database, set `SHOPWISE_DB_PATH` to its absolute path before starting the app. Set `SHOPPING_AUTH_DB` to override the accounts database path. Both files must already exist.

## Configuration and secrets

AI chat is optional; browsing and basic application startup do not need a Gemini key. For local AI chat, copy `.env.example` to `.env` and set `GEMINI_API_KEY`. The application loads this file for the chat/agent flow. In deployments, provide secrets through the host's secret environment configuration instead of committing `.env`.

| Variable | Purpose | Default |
| --- | --- | --- |
| `GEMINI_API_KEY` | Gemini API credential; needed only for AI chat | Unset |
| `GEMINI_MODEL` | Gemini model name | `gemini-3.8-flash` |
| `GEMINI_TIMEOUT_SECONDS` | Request timeout, accepted range 5–300 seconds | `90` |
| `SHOPWISE_DB_PATH` | Absolute path to the existing shopping database | Project-root `shopping.db` |
| `SHOPPING_AUTH_DB` | Path to the existing accounts database | Project-root `accounts.sqlite3` |
| `SHOPWISE_LOG_LEVEL` | Python logging level | `INFO` |
| `SHOPWISE_CHAT_TIMING` | Enable timing diagnostics when set to `1` | Disabled |

Do not put credentials, database records, or real customer information in source files, CI variables, or test fixtures.

## Run the application

From the project root, start the Streamlit UI:

```powershell
python -m streamlit run app\ui\web_app.py
```

The startup validator checks both database files before rendering the login screen. Users can browse as guests; account-only data and order flows require an authenticated identity. Account registration expects an active, already-linked shopper record. Password recovery and external payment processing are not configured.

The Gemini client starts the FastMCP server as a local stdio subprocess when a chat request needs tools. The application supplies authenticated context to that process; do not launch a server with a user ID supplied by an untrusted caller. For standalone MCP inspection, use the MCP Inspector with `python -m app.mcp.mcp_server` as its command and arguments. Do not type ordinary text into the MCP server's protocol terminal.

## Tests and CI

Run all automated tests and the compilation check locally:

```powershell
python -m compileall -q app tests
python -m unittest discover -s tests -v
```

Tests use isolated temporary SQLite fixtures. The MCP subprocess test also points the child server at its temporary fixture using `SHOPWISE_DB_PATH`; the suite does not need the local databases or a Gemini API key. `tests/test_gemini.py` is a manual live-API diagnostic and is not part of `unittest` discovery; it requires network access and a Gemini key, and should not be used with secrets in shared logs.

GitHub Actions runs the compilation check and complete unittest suite on pushes to `main` and pull requests targeting `main`. It installs the pinned direct dependencies on Python 3.11 and does not configure API secrets or use production databases. The workflow is `.github/workflows/tests.yml`.

## Deployment considerations and limitations

- Keep both database files on durable storage with restrictive file permissions. Streamlit startup requires them to exist and match the expected schema.
- SQLite is suited to this local/small deployment model. Writes serialize, and the application waits up to five seconds for a busy database; sustained concurrent write traffic may still fail. Use a single application instance with local persistent storage. Network filesystems, ephemeral disks, and horizontally scaled replicas are not a supported production database/session setup.
- Streamlit session state and login throttling are process-local. The throttle is best-effort and resets on process restart; it is not a distributed rate limiter. Multiple workers or replicas need shared session and throttling infrastructure.
- Configure Gemini credentials through a secret manager/environment variable, restrict their access, and monitor API usage. AI chat depends on external network and Gemini availability.
- Establish tested, access-controlled backups and a recovery procedure for both SQLite files. Do not copy live database files without a consistent SQLite backup method.
- This repository does not include a deployment platform, container setup, payment provider, email-based account recovery, distributed session store, or production identity provider. Passing CI is not a production-readiness certification.
