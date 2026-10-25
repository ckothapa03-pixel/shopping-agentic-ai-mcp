# LLM Integration Guide

This project already connects a Google Gemini language model to a local
shopping catalog through an MCP server. This guide explains how the pieces
work and how to run the existing checks.

## What is an LLM?

A large language model (LLM) is software trained to understand and produce
natural language. This project uses Google Gemini so shoppers can ask for
products in everyday language. Gemini can decide when to search the catalog,
and the application uses the actual database results when presenting products.

## Architecture

```text
app/ui/web_app.py --> app/ui/chat/chat.py --> app/agent/chat_runtime.py --\
                                                                           +--> app/agent/agent.py <--> app/agent/gemini.py
app/agent/agent_cli.py ---------------------------------------------------/          |
                                                                                     +--> app/mcp/mcp_tools.py
                                                                                               |
                                                                                     app/mcp/mcp_server.py
                                                                                               |
                                                                                     app/tools/products_tool.py
                                                                                               |
                                                                                     app/db/products.py
                                                                                               |
                                                                                     app/db/database.py --> shopping.db
```

## How the agent is connected

`app/agent/chat_runtime.py` starts the Gemini client and, for catalog requests, the
MCP server session used by the Streamlit application. `app/agent/agent_cli.py` owns
the terminal input/output loop and the equivalent client/session lifecycle
for the command-line interface. Both call `app/agent/agent.py` to run the response
loop, which coordinates model requests and tool results.

`app/agent/gemini.py` owns Gemini request configuration, timeout handling, and
stream-event parsing. `app/mcp/mcp_tools.py` adapts MCP tool descriptions, calls,
and results for the agent. The model can be selected with `GEMINI_MODEL`;
otherwise the existing default model is used.

## API key handling

The runtime loads settings from the project-root `.env` file, then reads
`GEMINI_API_KEY` from the environment. The key is passed to the GenAI client;
it is not printed as part of normal operation. The CLI redacts the key from
errors it displays. The project's `.gitignore` excludes `.env` files.

Keep the key private: do not paste it into chat, source files, screenshots, or
commits. Set it only in your local environment configuration.

## How Gemini calls `search_products`

When the agent starts a response, it asks the MCP server which tools are
available. The server reports the `search_products` tool, its description,
and its input fields. The agent provides that information to Gemini as
function-tool details.

Gemini can then request a product search and specify arguments such as a
search term, maximum price, minimum rating, stock requirement, or result
limit. The agent executes the requested MCP tool call and returns the result
to Gemini. The agent also checks that a supplied maximum price is a
non-negative number and limits the number of tool-call rounds.

For a budget-shopping request without an amount, the agent asks the shopper
for the maximum budget before calling Gemini or searching. This allows the
shopper to provide the amount in a follow-up message.

## How the MCP tool searches SQLite

`app/mcp/mcp_server.py` registers `search_products` with FastMCP and forwards its
arguments to the application tool layer. `app/tools/products_tool.py`
validates the result limit and calls the database search function.

`app/db/products.py` builds a parameterized SQLite query. It can search
product names, descriptions, SKUs, brands, and categories, and apply price,
rating, and in-stock filters. It returns matching rows with product details.
`app/db/database.py` opens `shopping.db` in the project root and configures
SQLite rows so they can be returned as dictionaries.

The Streamlit catalog interface is organized under `app/ui/`. Cached
catalog queries live in `app/ui/catalog_data.py`; page rendering is kept
separate from the database query implementation.
Login and store styles are stored in `assets/css/` and loaded by
`app/ui/styles.py`.

## From database results to the shopper's answer

After the MCP call finishes, the agent passes its result back to Gemini as a
function result. Gemini can use that result to write a natural-language
response. The agent also formats the returned catalog rows with fields such
as name, price, rating, stock availability, brand, and category. This helps
keep product details grounded in the database instead of relying on generated
claims.

Conversation history is held in memory by the running command-line agent, so
follow-up messages can refer to earlier messages during that run. It is not
persisted by this application after the agent exits.

## Example: search within ₹1,000

1. Start the agent and ask to find products within a budget, without giving an
   amount.
2. The agent asks, “What is your maximum budget in rupees?” It does not search
   yet.
3. Reply with `1000`.
4. Gemini receives the earlier request and the budget reply, then can call
   `search_products` with `max_price` set to `1000`.
5. The MCP server passes that request through the application tool to the
   SQLite query.
6. The matching catalog rows return through MCP to the agent and then to
   Gemini.
7. Gemini produces a short response, and the agent includes a formatted list
   of the matching product details returned by the database.

The budget clarification is handled directly by the agent. The subsequent
product search and response use the normal Gemini and MCP tool-calling flow.

## Important project files

| File | Role |
| --- | --- |
| `app/agent/agent.py` | Gemini/MCP response orchestration, conversation history, budget clarification, and tool-call handling. |
| `app/agent/chat_runtime.py` | Gemini client and MCP session setup for Streamlit chat. |
| `app/agent/agent_cli.py` | Terminal input/output loop and Gemini/MCP session setup for the CLI. |
| `app/agent/gemini.py` | Gemini request configuration, timeout handling, and stream parsing. |
| `app/mcp/mcp_server.py` | MCP server that exposes the `search_products` tool. |
| `app/mcp/mcp_tools.py` | Agent-side MCP tool discovery, calls, and result adaptation. |
| `app/tools/products_tool.py` | Application-level search interface and result-limit validation. |
| `app/db/products.py` | Builds and runs the SQLite product search with optional filters. |
| `app/db/database.py` | Locates `shopping.db` and creates SQLite connections. |
| `shopping.db` | Local SQLite product catalog. |
| `main.py` | Starts the MCP server directly. |
| `requirements.txt` | Lists the existing Python dependencies, including Gemini, dotenv, and MCP. |
| `.env` | Local environment configuration for the Gemini key and optional model setting. Keep this file private. |
| `.gitignore` | Excludes environment files, virtual environments, and the local database from version control. |
| `tests/test_agent.py` | Tests agent behavior, including MCP tool-call handling and the budget conversation flow. |
| `tests/test_user_story_7.py` | Tests database-backed product search, filters, limits, and returned fields. |
| `examples/demo_product_search.py` | Demonstration script that prints product results; it is not an automated unit-test suite. |

The MCP version is pinned in `requirements.txt`. This guide does not require
changing dependencies or the MCP version.

## Run the existing checks and agent

Run these commands from the project root using the Python environment where
the project's existing dependencies are installed.

To run the agent and User Story 7 automated tests:

```powershell
python -m unittest tests.test_agent tests.test_user_story_7
```

To start the interactive Gemini assistant:

```powershell
& ..\.venv\Scripts\python.exe -m app.agent.agent_cli
```

The agent requires a valid `GEMINI_API_KEY` in its environment configuration.
Type `exit` to stop the chat. The agent sends requests to Gemini, and product
searches may display local catalog results in the terminal.

`examples/demo_product_search.py` is a demonstration script that prints real product
details; it is not part of the automated unittest suite. Do not run it if you do
not want catalog records displayed. To run it from the project root, use
`python examples\demo_product_search.py`.

Start the Streamlit website from the project root with:

```powershell
& ..\.venv\Scripts\python.exe -m streamlit run app\ui\web_app.py
```

To open the MCP server in Inspector from the project root, use:

```powershell
$python = (Resolve-Path ..\.venv\Scripts\python.exe).Path
npx -y @modelcontextprotocol/inspector $python -m app.mcp.mcp_server
```

## Verification status

**Results supplied for this guide:** 13 automated tests passed, and a live
budget-search request returned product results.

**Not rerun while preparing this document:** Commands were not run, and the
application was not started for this documentation task. Therefore those
results are reported as supplied, not independently verified here.

The supplied results do not by themselves establish that every possible
Gemini request, error case, or deployment environment has been tested.
