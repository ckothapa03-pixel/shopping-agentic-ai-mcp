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
pip install -r requirements.txt
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

From the project root in PowerShell, make sure `uv` is on `PATH`. In this
workspace, `uv.exe` is inside the virtual environment one folder above the
project:

```powershell
$env:PATH = (Resolve-Path ..\venv\Scripts).Path + ";" + $env:PATH
mcp dev --with "mcp[cli]==1.30.0" app/mcp_server.py
```

The `--with` option includes the CLI dependencies needed by the Inspector-
launched server process and pins it to MCP 1.30.0. Do not remove the version
pin or change it to MCP 2.x.

Open the Inspector URL printed by the command and connect to **Shopping
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
```

The returned data comes from `shopping.db`.

## Important

Do not run:

```powershell
python app/mcp_server.py
```

and then type normal text into that terminal. MCP uses its communication protocol on stdin/stdout.

For normal testing, use the pinned Inspector command from section 5.

## Run the AI assistant

Create a `.env` file in the project root (it is excluded from version control)
and add your Gemini API key:

```text
GEMINI_API_KEY=replace-with-your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
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

## Run tests

```powershell
python -m unittest test_agent test_database
```

The MCP server remains independently runnable through the MCP Inspector steps
above.
