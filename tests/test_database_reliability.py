import hashlib
import sqlite3
import time
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import app.db.database as database
from app.db.schema import _validate_database, validate_account_schema, validate_shopping_schema
from tests.database_fixture import create_shopwise_databases, isolated_database_path


class DatabaseConnectionTests(unittest.TestCase):
    def setUp(self) -> None:
        original_path = database.DB_PATH
        self.addCleanup(setattr, database, "DB_PATH", original_path)
        self.shopping_db, self.account_db = create_shopwise_databases(self)
        database.DB_PATH = self.shopping_db

    def test_connections_apply_busy_timeout_and_foreign_keys(self) -> None:
        for connector in (database.get_connection, database.get_writable_connection):
            with closing(connector()) as connection:
                self.assertEqual(connection.execute("PRAGMA busy_timeout").fetchone()[0], 5000)
                self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_read_connection_cannot_write(self) -> None:
        with closing(database.get_connection()) as connection:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("DELETE FROM products")

    def test_closing_after_failure_rolls_back_and_closes_connection(self) -> None:
        connection = database.get_writable_connection()
        with closing(database.get_connection()) as original_connection:
            original_stock = original_connection.execute(
                "SELECT stock FROM products WHERE id=1"
            ).fetchone()[0]
        with self.assertRaisesRegex(RuntimeError, "simulated failure"):
            with closing(connection) as active:
                active.execute("BEGIN IMMEDIATE")
                active.execute("UPDATE products SET stock=stock-1 WHERE id=1")
                raise RuntimeError("simulated failure")
        with closing(database.get_connection()) as read_connection:
            actual_stock = read_connection.execute(
                "SELECT stock FROM products WHERE id=1"
            ).fetchone()[0]
        self.assertEqual(actual_stock, original_stock)
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_missing_database_is_never_created(self) -> None:
        missing = Path(tempfile.gettempdir()) / f"shopwise-missing-{uuid4().hex}.sqlite3"
        with self.assertRaises(FileNotFoundError):
            database.connect_writable(missing)
        with self.assertRaises(FileNotFoundError):
            database.connect_readonly(missing)
        self.assertFalse(missing.exists())

    def test_lock_wait_is_bounded_by_configured_busy_timeout(self) -> None:
        with patch.object(database, "SQLITE_BUSY_TIMEOUT_MS", 100):
            first = database.get_writable_connection()
            second = database.get_writable_connection()
        try:
            first.execute("BEGIN IMMEDIATE")
            started = time.perf_counter()
            with self.assertRaisesRegex(sqlite3.OperationalError, "locked"):
                second.execute("BEGIN IMMEDIATE")
            self.assertGreaterEqual(time.perf_counter() - started, 0.08)
            self.assertLess(time.perf_counter() - started, 1.0)
        finally:
            first.rollback()
            first.close()
            second.close()

    def test_schema_validation_accepts_fixtures_without_altering_them(self) -> None:
        shopping_hash = hashlib.sha256(self.shopping_db.read_bytes()).hexdigest()
        account_hash = hashlib.sha256(self.account_db.read_bytes()).hexdigest()
        with (
            patch("app.db.schema.DB_PATH", self.shopping_db),
            patch("app.db.schema._account_database_path", return_value=self.account_db),
        ):
            validate_shopping_schema()
            validate_account_schema()
        self.assertEqual(hashlib.sha256(self.shopping_db.read_bytes()).hexdigest(), shopping_hash)
        self.assertEqual(hashlib.sha256(self.account_db.read_bytes()).hexdigest(), account_hash)

    def test_schema_validation_reports_missing_columns_without_writing(self) -> None:
        path = isolated_database_path(self)
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE users (user_id TEXT)")
            connection.commit()
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(RuntimeError, "is_active"):
            _validate_database(path, {"users": {"user_id", "is_active"}})
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
