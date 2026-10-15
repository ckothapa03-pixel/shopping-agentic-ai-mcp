# Agentic AI Shopping Project

This project includes an AI shopping assistant connected to the local MCP
product-search server:

Shopper
        |
        v
AI Agent (Gemini)
        |
        v
MCP Server / search_products()
        |
        v
products_tool.py
        |
        v
products.py
        |
        v
shopping.db (SQLite)

## 1. Create virtual environment

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

## 2. Install dependencies

```powershell
python -m pip install --upgrade -r requirements.txt
```

## 3. Put `shopping.db` in the project root

The structure must be:

```text
agentic-ai-project/
├── app/
├── shopping.db
├── main.py
├── test_database.py
├── requirements.txt
└── .env
```

## 4. Test the database first

```powershell
python test_database.py
```

You should see products from the real `shopping.db`.

## 5. Test through MCP Inspector

From the project root in PowerShell, start the Inspector with the existing
Python environment and MCP 1.30.0 server:

```powershell
$python = (Resolve-Path ..\.venv\Scripts\python.exe).Path
npx -y @modelcontextprotocol/inspector $python -m app.mcp_server
```

This runs the server with the project's existing MCP installation and fetches
the Inspector through `npx`; it does not change project dependencies or upgrade
MCP. Open the Inspector URL printed by the command and connect to **Shopping
Assistant**.

Then find the tool:

```text
search_products
```

Try:

```text
search_term = mouse
max_price = 1000
min_rating = 4
in_stock = true
limit = 20
```

The returned data comes from `shopping.db`; `limit` controls the maximum number
of returned products.

## Important

Do not run:

```powershell
python app/mcp_server.py
```

and then type normal text into that terminal. MCP uses its communication protocol on stdin/stdout.

For MCP testing, use the Inspector command from section 5.

## Run the AI assistant

Create a `.env` file in the project root (it is excluded from version control)
and add your Gemini API key:

```text
GEMINI_API_KEY=replace-with-your-gemini-api-key
GEMINI_MODEL=gemini-3.8-flash
```

Replace the placeholder with your key from Google AI Studio. Never commit the
real key.

Start the assistant from the project root:

```powershell
python -m app.agent
```

The Gemini-powered agent starts the MCP server over stdio, discovers its
available tools, and lets Gemini call `search_products` as needed. Type `exit`
to quit. The model can be changed with `GEMINI_MODEL`; the API key must never be
committed.

## Run tests and print real budget matches

```powershell
$python = (Resolve-Path ..\.venv\Scripts\python.exe).Path
& $python -m unittest test_agent test_user_story_7
& $python test_database.py
```

The first command runs the existing agent tests and User Story #7 tests. The
second prints actual products from `shopping.db` priced at ₹1,000 or less,
including price, rating, stock, brand, and category.

The MCP server remains independently runnable through the MCP Inspector steps
above.
