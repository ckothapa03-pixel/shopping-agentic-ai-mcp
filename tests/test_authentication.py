import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.shopping.authentication import authenticate_account, register_account

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS_SCHEMA_PATH = PROJECT_ROOT / "scripts" / "accounts_schema.sql"


class AccountAuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        file_descriptor, database_path = tempfile.mkstemp(
            prefix="accounts-auth-test-", suffix=".sqlite3", dir=PROJECT_ROOT
        )
        os.close(file_descriptor)
        self.database_path = Path(database_path)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.executescript(ACCOUNTS_SCHEMA_PATH.read_text(encoding="utf-8"))

    def tearDown(self) -> None:
        self.database_path.unlink(missing_ok=True)

    def test_registration_stores_a_hash_and_authentication_verifies_credentials(
        self,
    ) -> None:
        account = register_account(
            "Shopper@example.com",
            "correct-horse",
            "Demo Shopper",
            self.database_path,
        )

        self.assertEqual(
            account,
            {"email": "shopper@example.com", "full_name": "Demo Shopper"},
        )
        self.assertEqual(
            authenticate_account(
                "SHOPPER@example.com",
                "correct-horse",
                self.database_path,
            ),
            account,
        )
        self.assertIsNone(
            authenticate_account(
                "shopper@example.com",
                "wrong-password",
                self.database_path,
            )
        )

        with closing(sqlite3.connect(self.database_path)) as connection:
            salt, password_hash = connection.execute(
                "SELECT password_salt, password_hash FROM accounts"
            ).fetchone()
        self.assertNotEqual(password_hash, b"correct-horse")
        self.assertEqual(len(salt), 16)

    def test_rejects_duplicate_and_invalid_registration(self) -> None:
        register_account(
            "shopper@example.com",
            "correct-horse",
            "Demo Shopper",
            self.database_path,
        )

        with self.assertRaisesRegex(ValueError, "already exists"):
            register_account(
                "SHOPPER@example.com",
                "another-password",
                "Another Shopper",
                self.database_path,
            )
        with self.assertRaisesRegex(ValueError, "valid email"):
            register_account(
                "not-an-email",
                "correct-horse",
                "Demo Shopper",
                self.database_path,
            )
        with self.assertRaisesRegex(ValueError, "at least 8"):
            register_account(
                "new@example.com",
                "short",
                "Demo Shopper",
                self.database_path,
            )

    def test_authentication_does_not_create_missing_database_or_table(self) -> None:
        missing_database = self.database_path.with_name("missing-accounts.sqlite3")
        with self.assertRaises(FileNotFoundError):
            authenticate_account("shopper@example.com", "correct-horse", missing_database)
        self.assertFalse(missing_database.exists())

        file_descriptor, empty_database_name = tempfile.mkstemp(
            prefix="accounts-no-schema-test-",
            suffix=".sqlite3",
            dir=PROJECT_ROOT,
        )
        os.close(file_descriptor)
        empty_database = Path(empty_database_name)
        try:
            with self.assertRaisesRegex(sqlite3.OperationalError, "no such table"):
                authenticate_account(
                    "shopper@example.com",
                    "correct-horse",
                    empty_database,
                )
            with closing(sqlite3.connect(empty_database)) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall(),
                    [],
                )
        finally:
            empty_database.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
