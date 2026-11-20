import sqlite3
import unittest
from contextlib import closing, contextmanager
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4
from unittest.mock import patch

from app.shopping import authentication
from app.shopping.authentication import authenticate_account, register_account

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COLUMNS = {
    "email",
    "full_name",
    "password_salt",
    "password_hash",
    "created_at",
}


class _FakeCursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _FakeConnection:
    def __init__(self):
        self.accounts = {}

    def execute(self, query, parameters):
        if query.lstrip().startswith("INSERT INTO accounts"):
            email, full_name, salt, password_hash = parameters
            if email in self.accounts:
                raise sqlite3.IntegrityError("duplicate email")
            self.accounts[email] = {
                "email": email,
                "full_name": full_name,
                "password_salt": salt,
                "password_hash": password_hash,
            }
            return _FakeCursor(None)

        if query.lstrip().startswith("SELECT email, full_name"):
            return _FakeCursor(self.accounts.get(parameters[0]))

        raise AssertionError(f"Unexpected authentication query: {query}")


class AccountAuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = _FakeConnection()

    @contextmanager
    def _fake_account_connection(self, _db_path):
        yield self.connection

    def test_registration_stores_a_hash_and_authentication_verifies_credentials(
        self,
    ) -> None:
        shopping_user = {
            "user_id": "USR-TEST",
            "full_name": "Demo Shopper",
            "email": "shopper@example.com",
            "is_active": True,
        }
        with (
            patch.object(
                authentication,
                "_account_connection",
                self._fake_account_connection,
            ),
            patch.object(
                authentication,
                "resolve_shopping_user",
                return_value=shopping_user,
            ),
        ):
            account = register_account(
                "Shopper@example.com",
                "correct-horse",
                "Demo Shopper",
            )
            self.assertEqual(
                account,
                {
                    "email": "shopper@example.com",
                    "full_name": "Demo Shopper",
                    "user_id": "USR-TEST",
                },
            )
            self.assertEqual(
                authenticate_account("SHOPPER@example.com", "correct-horse"),
                account,
            )
            self.assertIsNone(
                authenticate_account("shopper@example.com", "wrong-password")
            )

        stored_account = self.connection.accounts["shopper@example.com"]
        self.assertNotEqual(stored_account["password_hash"], b"correct-horse")
        self.assertEqual(len(stored_account["password_salt"]), 16)

    def test_rejects_duplicate_and_invalid_registration(self) -> None:
        shopping_user = {
            "user_id": "USR-TEST",
            "full_name": "Demo Shopper",
            "email": "shopper@example.com",
            "is_active": True,
        }
        with (
            patch.object(
                authentication,
                "_account_connection",
                self._fake_account_connection,
            ),
            patch.object(
                authentication,
                "resolve_shopping_user",
                return_value=shopping_user,
            ),
        ):
            register_account(
                "shopper@example.com",
                "correct-horse",
                "Demo Shopper",
            )
            with self.assertRaisesRegex(ValueError, "already exists"):
                register_account(
                    "SHOPPER@example.com",
                    "another-password",
                    "Another Shopper",
                )
            with self.assertRaisesRegex(ValueError, "valid email"):
                register_account(
                    "not-an-email",
                    "correct-horse",
                    "Demo Shopper",
                )
            with self.assertRaisesRegex(ValueError, "at least 8"):
                register_account("new@example.com", "short", "Demo Shopper")

    def test_existing_accounts_database_has_the_expected_columns(self) -> None:
        database_path = PROJECT_ROOT / "accounts.sqlite3"
        self.assertTrue(database_path.is_file())
        database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
        with closing(sqlite3.connect(database_uri, uri=True)) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertIn("accounts", tables)
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(accounts)")
            }
        self.assertEqual(columns, EXPECTED_COLUMNS)

    def test_authentication_does_not_create_a_missing_database(self) -> None:
        missing_database = Path(gettempdir()) / f"{uuid4().hex}.sqlite3"
        with self.assertRaises(FileNotFoundError):
            authenticate_account(
                "shopper@example.com",
                "correct-horse",
                missing_database,
            )
        self.assertFalse(missing_database.exists())


if __name__ == "__main__":
    unittest.main()
