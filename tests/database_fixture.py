"""Create disposable SQLite files without touching project data stores."""

from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def isolated_database_path(test_case: unittest.TestCase, suffix: str = ".sqlite3") -> Path:
    handle = tempfile.NamedTemporaryFile(
        prefix=".shopwise-test-",
        suffix=suffix,
        dir=PROJECT_ROOT,
        delete=False,
    )
    path = Path(handle.name)
    handle.close()
    test_case.addCleanup(path.unlink, missing_ok=True)
    return path


def create_shopwise_databases(
    test_case: unittest.TestCase,
    product_count: int = 20,
) -> tuple[Path, Path]:
    """Create small disposable shopping/account databases with catalog fixtures."""
    import sqlite3

    shopping_path = isolated_database_path(test_case, suffix="-shopping.db")
    account_path = isolated_database_path(test_case, suffix="-accounts.sqlite3")
    connection = sqlite3.connect(shopping_path)
    connection.executescript(
        """
        CREATE TABLE users (
            user_id TEXT PRIMARY KEY, full_name TEXT NOT NULL, email TEXT NOT NULL,
            phone TEXT, created_at TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL,
            description TEXT
        );
        CREATE TABLE brands (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE products (
            id INTEGER PRIMARY KEY, sku TEXT NOT NULL, name TEXT NOT NULL,
            description TEXT, category_id INTEGER NOT NULL, brand_id INTEGER NOT NULL,
            price REAL NOT NULL, mrp REAL NOT NULL, stock INTEGER NOT NULL,
            rating_avg REAL NOT NULL DEFAULT 0, rating_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE cart_items (
            user_id TEXT NOT NULL, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL,
            added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, product_id)
        );
        CREATE TABLE addresses (
            id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, label TEXT NOT NULL,
            line1 TEXT NOT NULL, city TEXT NOT NULL, state TEXT NOT NULL,
            pincode TEXT NOT NULL, is_default INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, address_id INTEGER,
            status TEXT NOT NULL, payment_method TEXT NOT NULL, coupon_code TEXT,
            subtotal REAL NOT NULL, discount REAL NOT NULL DEFAULT 0,
            shipping_fee REAL NOT NULL DEFAULT 0, total REAL NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL, unit_price REAL NOT NULL
        );
        CREATE TABLE coupons (
            code TEXT PRIMARY KEY, description TEXT NOT NULL,
            discount_percent INTEGER NOT NULL, min_order_value REAL NOT NULL DEFAULT 0,
            max_discount REAL NOT NULL, valid_until TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE wishlists (
            user_id TEXT NOT NULL, product_id INTEGER NOT NULL,
            added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, product_id)
        );
        CREATE TABLE reviews (
            id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL, user_id TEXT,
            rating INTEGER, title TEXT, body TEXT, created_at TEXT
        );
        CREATE TABLE rag_documents (
            id INTEGER PRIMARY KEY, source_name TEXT UNIQUE NOT NULL,
            document_type TEXT NOT NULL, content TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE rag_chunks (
            id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL, chunk_text TEXT NOT NULL
        );
        INSERT INTO users VALUES
            ('USR-TEST', 'Demo Shopper', 'demo@example.com', NULL, '2026-01-01', 1),
            ('USR-A', 'User A', 'a@example.com', NULL, '2026-01-01', 1),
            ('USR-B', 'User B', 'b@example.com', NULL, '2026-01-01', 1);
        INSERT INTO brands VALUES (1, 'Acme'), (2, 'Northstar'), (3, 'Everyday');
        """
    )
    for index in range(1, 11):
        connection.execute(
            "INSERT INTO categories VALUES (?, ?, ?, ?)",
            (index, f"Category {index:02d}", f"category-{index:02d}", "Test category"),
        )
    names = ["Wireless Mouse", "Wireless Keyboard", "Home Router", "Mesh Router"]
    featured_ids = (100, 64, 81, 80, 53, 60)
    product_ids = list(range(1, product_count + 1))
    for featured_id in featured_ids:
        if featured_id not in product_ids:
            product_ids.append(featured_id)
    for position, product_id in enumerate(product_ids):
        category_id = (position // 2) % 10 + 1
        name = names[product_id - 1] if product_id <= len(names) else f"Sample Product {product_id:03d}"
        brand_id = (product_id - 1) % 3 + 1
        price = 10 + product_id * 2.5
        rating = (
            4.95 - featured_ids.index(product_id) / 100
            if product_id in featured_ids
            else 3.5 + (position % 10) / 20
        )
        connection.execute(
            """
            INSERT INTO products
                (id, sku, name, description, category_id, brand_id, price, mrp,
                 stock, rating_avg, rating_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                f"SKU-{product_id:03d}",
                name,
                f"Fixture description for {name}",
                category_id,
                brand_id,
                price,
                price + 5,
                0 if product_id == 3 else 10,
                rating,
                product_id * 2,
                "2026-01-01",
            ),
        )
    connection.commit()
    connection.close()

    account_connection = sqlite3.connect(account_path)
    account_connection.executescript(
        """
        CREATE TABLE accounts (
            email TEXT PRIMARY KEY, full_name TEXT NOT NULL, password_salt BLOB NOT NULL,
            password_hash BLOB NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE identity_mappings (
            account_email TEXT PRIMARY KEY, user_id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    account_connection.commit()
    account_connection.close()
    return shopping_path, account_path
