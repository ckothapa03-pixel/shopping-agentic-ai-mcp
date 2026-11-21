import sqlite3
from decimal import Decimal
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from app.db.address_repository import (
    create_address,
    delete_address,
    get_address,
    list_addresses,
)
from app.db.checkout_repository import calculate_coupon_discount, create_order
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
from tests.database_fixture import isolated_database_path


class OwnedShoppingTests(unittest.TestCase):
    def setUp(self) -> None:
        original_db_path = database.DB_PATH
        self.addCleanup(setattr, database, "DB_PATH", original_db_path)
        self.db = isolated_database_path(self, suffix=".db")
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

    def _insert_coupon(
        self,
        code: str,
        *,
        percent: int = 10,
        minimum: float = 0,
        maximum: float = 1000,
        valid_until: str = "2999-12-31 23:59:59",
        active: int = 1,
    ) -> None:
        connection = sqlite3.connect(self.db)
        try:
            connection.execute(
                """
                INSERT INTO coupons
                    (code, description, discount_percent, min_order_value,
                     max_discount, valid_until, is_active)
                VALUES (?, 'Test coupon', ?, ?, ?, ?, ?)
                """,
                (code, percent, minimum, maximum, valid_until, active),
            )
            connection.commit()
        finally:
            connection.close()

    def _product_stock(self, product_id: int) -> int:
        connection = sqlite3.connect(self.db)
        try:
            return connection.execute(
                "SELECT stock FROM products WHERE id=?", (product_id,)
            ).fetchone()[0]
        finally:
            connection.close()

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
        self.assertEqual(result["total"], 200)
        self.assertEqual(len(list_orders("USR-A")), 1)
        self.assertEqual(get_cart("USR-A"), [])
        self.assertEqual(self._product_stock(1), 3)
        detail = get_order("USR-A", result["order_id"])
        self.assertEqual(len(detail["items"]), 1)
        self.assertEqual(detail["items"][0]["unit_price"], 100)
        canceled = cancel_order("USR-A", result["order_id"])
        self.assertEqual(canceled["status"], "CANCELLED")
        self.assertEqual(self._product_stock(1), 5)
        with self.assertRaisesRegex(ValueError, "cannot be cancelled"):
            cancel_order("USR-A", result["order_id"])
        self.assertEqual(self._product_stock(1), 5)

    def test_coupon_validation_checks_expiry_status_minimum_and_discount_cap(self) -> None:
        self._insert_coupon("VALID", percent=15, minimum=50, maximum=10)
        self._insert_coupon("EXPIRED", valid_until="2000-01-01 00:00:00")
        self._insert_coupon("INACTIVE", active=0)
        self._insert_coupon("FULL", percent=100, maximum=1000)
        connection = sqlite3.connect(self.db)
        connection.execute(
            """
            INSERT INTO coupons
                (code, description, discount_percent, min_order_value,
                 max_discount, valid_until, is_active)
            VALUES ('BOUNDARY', 'Boundary', 10, 0, 1000, CURRENT_TIMESTAMP, 1)
            """
        )
        connection.commit()
        connection.close()

        self.assertEqual(
            calculate_coupon_discount(Decimal("100"), " valid "),
            Decimal("10.00"),
        )
        with self.assertRaisesRegex(ValueError, "expired"):
            calculate_coupon_discount(Decimal("100"), "EXPIRED")
        with self.assertRaisesRegex(ValueError, "expired"):
            calculate_coupon_discount(Decimal("100"), "BOUNDARY")
        with self.assertRaisesRegex(ValueError, "inactive"):
            calculate_coupon_discount(Decimal("100"), "INACTIVE")
        with self.assertRaisesRegex(ValueError, "invalid"):
            calculate_coupon_discount(Decimal("100"), "MISSING")
        with self.assertRaisesRegex(ValueError, "minimum"):
            calculate_coupon_discount(Decimal("40"), "VALID")
        self.assertEqual(
            calculate_coupon_discount(Decimal("40"), "FULL"),
            Decimal("40.00"),
        )

    def test_coupon_expiring_after_review_is_rejected_at_order_creation(self) -> None:
        address = create_address("USR-A", "Home", "1 Main Road", "City", "State", "123456", True)
        set_cart_quantity("USR-A", 1, 1)
        self._insert_coupon("FLASH", percent=10)
        reviewed_discount = calculate_coupon_discount(Decimal("100"), "FLASH")
        self.assertEqual(reviewed_discount, Decimal("10.00"))

        connection = sqlite3.connect(self.db)
        connection.execute(
            "UPDATE coupons SET valid_until=? WHERE code=?",
            ("2000-01-01 00:00:00", "FLASH"),
        )
        connection.commit()
        connection.close()

        with self.assertRaisesRegex(ValueError, "expired"):
            create_order(
                "USR-A",
                address["id"],
                coupon_code="FLASH",
                expected_cart=[(1, 1, "100.00")],
                expected_total=Decimal("90.00"),
            )
        self.assertEqual(len(list_orders("USR-A")), 0)
        self.assertEqual(get_cart("USR-A")[0]["quantity"], 1)

    def test_coupon_discount_and_persisted_total_use_cents(self) -> None:
        address = create_address("USR-A", "Home", "1 Main Road", "City", "State", "123456", True)
        set_cart_quantity("USR-A", 1, 1)
        self._insert_coupon("ROUND15", percent=15)
        connection = sqlite3.connect(self.db)
        connection.execute("UPDATE products SET price=100.05 WHERE id=1")
        connection.commit()
        connection.close()

        discount = calculate_coupon_discount(Decimal("100.05"), "ROUND15")
        self.assertEqual(discount, Decimal("15.01"))
        result = create_order(
            "USR-A",
            address["id"],
            coupon_code="ROUND15",
            expected_cart=[(1, 1, "100.05")],
            expected_total=Decimal("85.04"),
        )
        self.assertEqual(result["subtotal"], 100.05)
        self.assertEqual(result["discount"], 15.01)
        self.assertEqual(result["total"], 85.04)
        detail = get_order("USR-A", result["order_id"])
        self.assertEqual(detail["items"][0]["unit_price"], 100.05)

    def test_stock_is_rechecked_and_cannot_become_negative(self) -> None:
        address = create_address("USR-A", "Home", "1 Main Road", "City", "State", "123456", True)
        set_cart_quantity("USR-A", 1, 5)
        connection = sqlite3.connect(self.db)
        connection.execute(
            "UPDATE cart_items SET quantity=6 WHERE user_id='USR-A' AND product_id=1"
        )
        connection.commit()
        connection.close()

        with self.assertRaisesRegex(ValueError, "exceeds current stock"):
            create_order("USR-A", address["id"])
        self.assertEqual(len(list_orders("USR-A")), 0)
        self.assertEqual(self._product_stock(1), 5)

    def test_concurrent_checkouts_cannot_create_duplicate_orders_or_oversell(self) -> None:
        address = create_address("USR-A", "Home", "1 Main Road", "City", "State", "123456", True)
        set_cart_quantity("USR-A", 1, 1)
        start = Barrier(2)

        def place_order():
            start.wait()
            try:
                return create_order("USR-A", address["id"])
            except ValueError as error:
                return str(error)

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _index: place_order(), range(2)))

        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertEqual(len(list_orders("USR-A")), 1)
        self.assertEqual(self._product_stock(1), 4)

    def test_price_change_after_review_invalidates_snapshot(self) -> None:
        address = create_address("USR-A", "Home", "1 Main Road", "City", "State", "123456", True)
        set_cart_quantity("USR-A", 1, 1)
        connection = sqlite3.connect(self.db)
        connection.execute("UPDATE products SET price=125.50 WHERE id=1")
        connection.commit()
        connection.close()

        with self.assertRaisesRegex(ValueError, "cart changed"):
            create_order(
                "USR-A",
                address["id"],
                expected_cart=[(1, 1, "100.00")],
                expected_total=Decimal("100.00"),
            )
        self.assertEqual(len(list_orders("USR-A")), 0)
        self.assertEqual(get_cart("USR-A")[0]["quantity"], 1)

    def test_coupon_terms_changed_after_review_invalidate_expected_total(self) -> None:
        address = create_address("USR-A", "Home", "1 Main Road", "City", "State", "123456", True)
        set_cart_quantity("USR-A", 1, 1)
        self._insert_coupon("CHANGED", percent=10)
        reviewed_discount = calculate_coupon_discount(Decimal("100"), "CHANGED")
        self.assertEqual(reviewed_discount, Decimal("10.00"))
        connection = sqlite3.connect(self.db)
        connection.execute(
            "UPDATE coupons SET discount_percent=20 WHERE code='CHANGED'"
        )
        connection.commit()
        connection.close()

        with self.assertRaisesRegex(ValueError, "total changed"):
            create_order(
                "USR-A",
                address["id"],
                coupon_code="CHANGED",
                expected_cart=[(1, 1, "100.00")],
                expected_total=Decimal("90.00"),
            )
        self.assertEqual(len(list_orders("USR-A")), 0)
        self.assertEqual(self._product_stock(1), 5)

    def test_order_failure_rolls_back_order_items_inventory_and_cart(self) -> None:
        address = create_address("USR-A", "Home", "1 Main Road", "City", "State", "123456", True)
        set_cart_quantity("USR-A", 1, 1)
        connection = sqlite3.connect(self.db)
        connection.execute(
            """
            CREATE TRIGGER reject_test_order_item BEFORE INSERT ON order_items
            BEGIN SELECT RAISE(ABORT, 'test order item failure'); END
            """
        )
        connection.commit()
        connection.close()

        with self.assertRaisesRegex(sqlite3.IntegrityError, "test order item failure"):
            create_order("USR-A", address["id"])
        self.assertEqual(len(list_orders("USR-A")), 0)
        self.assertEqual(get_cart("USR-A")[0]["quantity"], 1)
        connection = sqlite3.connect(self.db)
        try:
            self.assertEqual(
                connection.execute("SELECT stock FROM products WHERE id=1").fetchone()[0],
                5,
            )
        finally:
            connection.close()

    def test_checkout_confirmation_cart_snapshot_is_checked_transactionally(self) -> None:
        address = create_address("USR-A", "Home", "1 Main Road", "City", "State", "123456", True)
        set_cart_quantity("USR-A", 1, 2)
        with self.assertRaisesRegex(ValueError, "cart changed"):
            create_order(
                "USR-A",
                address["id"],
                "COD",
                expected_cart=[(1, 1, "100.0")],
            )
        self.assertEqual(len(list_orders("USR-A")), 0)
        self.assertEqual(get_cart("USR-A")[0]["quantity"], 2)
        with self.assertRaisesRegex(ValueError, "total changed"):
            create_order(
                "USR-A",
                address["id"],
                "COD",
                expected_cart=[(1, 2, "100.0")],
                expected_total=Decimal("199"),
            )
        self.assertEqual(len(list_orders("USR-A")), 0)
        result = create_order(
            "USR-A",
            address["id"],
            "COD",
            expected_cart=[(1, 2, "100.0")],
            expected_total=Decimal("200"),
        )
        self.assertEqual(result["subtotal"], 200)

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
