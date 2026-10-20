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
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 2. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

Python 3.10 or newer is required. The project keeps its existing
`mcp[cli]==1.30.0` pin.

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

From the project root in PowerShell, start the Inspector with the project
virtual environment:

```powershell
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
npx -y @modelcontextprotocol/inspector $python -m app.mcp_server
```

The Inspector is fetched through `npx`; this does not change project
dependencies or upgrade MCP. Open the Inspector URL printed by the command and
connect to **Shopping Assistant**.

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

For a budget search, you can enter the user story without an amount:

```text
As a shopper, I want to search for products within my budget so that I can find affordable products easily.
```

The agent asks for your maximum budget in rupees. Enter the amount (for example,
`1000`) in your next message. Gemini uses the conversation context to call
`search_products` with that amount as `max_price`. The agent displays product
rows returned by the catalog with name, price, rating, stock availability,
brand, and category. These details come from the MCP tool and `shopping.db`, not
generated product claims.

## Run the shopping website

From the project root, activate the virtual environment and start Streamlit:

```powershell
Set-Location "C:\path\to\agentic-ai-project"
.\.venv\Scripts\Activate.ps1
python -m streamlit run app\web_app.py
```

Replace the example path with the current project folder. The first screen is
login; select **Continue as Guest** to browse without registering. Search,
categories, brands, price bounds, customer ratings, stock, sorting, and grid or
list layouts use the real catalog rows in `shopping.db`. The cart and saved
products are available from the top-right controls. The floating Shopwise AI
button opens the Gemini/MCP product-search assistant.

Account registration stores salted password hashes in the ignored
`accounts.sqlite3`, separate from `shopping.db`. Existing shopper rows in the
catalog database have no password credentials and cannot be used to sign in.
This local demo flow is not production identity management; it has no password
reset or login rate limiting. The website does not read or display customer or
order records from `shopping.db`.

### Demonstration behavior and limitations

- Cart and wishlist data are temporary to the current browser session for
  guests and signed-in demo accounts. The app does not read or write the
  database `cart_items` table.
- **Demo checkout** rechecks current product availability, stock, and price,
  then calculates totals from catalog data. It does not save an order or charge
  a payment method. Real order creation is not available because the demo
  account store is separate from the existing users, address, and order data.
- `shopping.db` has no image field and no product image assets are supplied;
  product cards use a neutral image-unavailable placeholder.
- Orders are not shown in the navigation because account-to-order ownership is
  not integrated.
- AI chat requires a usable Gemini key and network access. It reuses the
  existing Gemini agent and MCP `search_products` path; failures are reported
  without claiming an unverified search succeeded.
- No database schema migration or record changes are required.

Keep `.env` private and do not use real account credentials for this local
demonstration. The command-line agent remains available with
`python -m app.agent`.

## Run tests

```powershell
python -m unittest test_agent test_user_story_7 test_catalog test_cart test_web_app test_authentication test_web_navigation
```

This runs the agent, catalog, cart/checkout, authentication, grounded-chat,
and login/guest/navigation tests. The agent budget-flow test uses a
deterministic model fixture while starting the real MCP server and querying
`shopping.db`; it does not require a Gemini API key. `test_database.py` is an
optional demonstration script that prints product data, not an automated test.

The MCP server remains independently runnable through the MCP Inspector steps
above.
