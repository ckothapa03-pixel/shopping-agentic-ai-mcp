import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.db.address_repository import (
    create_address,
    delete_address,
    get_address,
    list_addresses,
)
from app.db.checkout_repository import create_order
from app.db.order_repository import cancel_order, get_order, list_orders
from app.db.user_data import (
    clear_cart,
    get_cart,
    remove_cart_item,
    set_cart_quantity,
)
import app.db.database as database
import app.db.address_repository as address_repository
import app.db.checkout_repository as checkout_repository
import app.db.order_repository as order_repository
import app.db.user_data as user_data


class OwnedShoppingTests(unittest.TestCase):
    def setUp(self) -> None:
        original_db_path = database.DB_PATH
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.addCleanup(setattr, database, "DB_PATH", original_db_path)
        self.db = Path(temporary_directory.name) / "shopping.db"
        connection = sqlite3.connect(self.db)
        connection.executescript(
            """
            CREATE TABLE users (
                user_id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                created_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE products (
                id INTEGER PRIMARY KEY,
                sku TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                category_id INTEGER NOT NULL,
                brand_id INTEGER NOT NULL,
                price REAL NOT NULL,
                mrp REAL NOT NULL,
                stock INTEGER NOT NULL,
                rating_avg REAL NOT NULL DEFAULT 0,
                rating_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                description TEXT
            );
            CREATE TABLE brands (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );
            CREATE TABLE cart_items (
                user_id TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, product_id)
            );
            CREATE TABLE addresses (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                label TEXT NOT NULL,
                line1 TEXT NOT NULL,
                city TEXT NOT NULL,
                state TEXT NOT NULL,
                pincode TEXT NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                address_id INTEGER,
                status TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                coupon_code TEXT,
                subtotal REAL NOT NULL,
                discount REAL NOT NULL DEFAULT 0,
                shipping_fee REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE order_items (
                id INTEGER PRIMARY KEY,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL
            );
            CREATE TABLE coupons (
                code TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                discount_percent INTEGER NOT NULL,
                min_order_value REAL NOT NULL DEFAULT 0,
                max_discount REAL NOT NULL,
                valid_until TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE wishlists (
                user_id TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, product_id)
            );
            INSERT INTO users VALUES ('USR-A','User A','a@example.com',NULL,'2026-01-01',1);
            INSERT INTO users VALUES ('USR-B','User B','b@example.com',NULL,'2026-01-01',1);
            INSERT INTO categories (id,name,slug) VALUES (1,'Test','test');
            INSERT INTO brands (id,name) VALUES (1,'Test Brand');
            INSERT INTO products
                (id,sku,name,description,category_id,brand_id,price,mrp,stock,rating_avg,rating_count,created_at)
            VALUES
                (1,'SKU-1','Product One','Description',1,1,100,120,5,4.5,10,'2026-01-01'),
                (2,'SKU-2','Product Two','Description',1,1,200,250,0,4,5,'2026-01-01');
            """
        )
        connection.commit()
        connection.close()

        database.DB_PATH = self.db
        patches = (
            patch.object(address_repository, "get_writable_connection", database.get_writable_connection),
            patch.object(user_data, "get_writable_connection", database.get_writable_connection),
            patch.object(user_data, "get_connection", database.get_connection),
            patch.object(checkout_repository, "get_writable_connection", database.get_writable_connection),
            patch.object(order_repository, "get_writable_connection", database.get_writable_connection),
            patch.object(order_repository, "get_connection", database.get_connection),
        )
        self.patchers = patches
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_address_crud_is_owned_and_default_is_preserved(self) -> None:
        address = create_address("USR-A", "Home", "1 Main Road", "City", "State", "123456", True)
        self.assertEqual(address["user_id"], "USR-A")
        self.assertIsNone(get_address("USR-B", address["id"]))
        self.assertEqual(len(list_addresses("USR-A")), 1)
        delete_address("USR-A", address["id"])
        self.assertEqual(list_addresses("USR-A"), [])

    def test_cart_requires_active_identity_and_stock(self) -> None:
        set_cart_quantity("USR-A", 1, 2)
        self.assertEqual(get_cart("USR-A")[0]["quantity"], 2)
        with self.assertRaises(ValueError):
            set_cart_quantity("USR-A", 1, 6)
        remove_cart_item("USR-A", 1)
        clear_cart("USR-A")

    def test_checkout_create_order_items_and_cancel_transactionally(self) -> None:
        address = create_address("USR-A", "Home", "1 Main Road", "City", "State", "123456", True)
        set_cart_quantity("USR-A", 1, 2)
        result = create_order("USR-A", address["id"], "COD")
        self.assertEqual(result["subtotal"], 200)
        self.assertEqual(len(list_orders("USR-A")), 1)
        detail = get_order("USR-A", result["order_id"])
        self.assertEqual(len(detail["items"]), 1)
        canceled = cancel_order("USR-A", result["order_id"])
        self.assertEqual(canceled["status"], "CANCELLED")
        self.assertEqual(get_cart("USR-A"), [])

    def test_cross_user_order_and_address_access_is_denied(self) -> None:
        address = create_address("USR-A", "Home", "1 Main Road", "City", "State", "123456", True)
        set_cart_quantity("USR-A", 1, 1)
        result = create_order("USR-A", address["id"], "COD")
        self.assertIsNone(get_order("USR-B", result["order_id"]))
        with self.assertRaises(PermissionError):
            cancel_order("USR-B", result["order_id"])
        self.assertIsNone(get_address("USR-B", address["id"]))


if __name__ == "__main__":
    unittest.main()
