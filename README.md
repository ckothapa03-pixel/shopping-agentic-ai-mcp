# Agentic AI Shopping Project

This is the first working layer of the project:

User / MCP Client
        |
        v
MCP Server
        |
        v
search_products()
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

## 2. Install dependency

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

## Current scope

This version intentionally does NOT include an LLM or AI API key.

After this MCP/database layer works, the next layer can be an Agent that decides when to call `search_products`.
