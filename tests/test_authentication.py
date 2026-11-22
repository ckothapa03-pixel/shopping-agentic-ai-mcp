import hashlib
import sqlite3
import unittest
from pathlib import Path
from tempfile import gettempdir
from unittest.mock import patch
from uuid import uuid4

from app.shopping.authentication import (
    REGISTRATION_UNAVAILABLE_MESSAGE,
    authenticate_account,
    register_account,
)
from app.db.schema import validate_account_schema
from tests.database_fixture import create_shopwise_databases

EXPECTED_COLUMNS = {
    "email",
    "full_name",
    "password_salt",
    "password_hash",
    "created_at",
}


class AccountAuthenticationTests(unittest.TestCase):
    def test_registration_fails_closed_without_email_ownership_proof(self) -> None:
        shopping_db, account_db = create_shopwise_databases(self)
        connection = sqlite3.connect(account_db)
        try:
            connection.execute(
                """
                INSERT INTO identity_mappings (account_email, user_id)
                VALUES (?, ?)
                """,
                ("shopper@example.com", "USR-TEST"),
            )
            connection.commit()
        finally:
            connection.close()

        before_hashes = {
            path: hashlib.sha256(path.read_bytes()).digest()
            for path in (shopping_db, account_db)
        }
        responses = []
        for email in ("shopper@example.com", "unmapped@example.com"):
            with self.assertRaises(ValueError) as error:
                register_account(
                    email,
                    "correct-horse",
                    "Demo Shopper",
                    db_path=account_db,
                    shopping_db_path=shopping_db,
                )
            responses.append(str(error.exception))
        self.assertEqual(responses, [REGISTRATION_UNAVAILABLE_MESSAGE] * 2)

        with self.assertRaises(TypeError):
            register_account(
                "shopper@example.com",
                "correct-horse",
                "Demo Shopper",
                db_path=account_db,
                shopping_db_path=shopping_db,
                user_id="USR-B",
            )

        self.assertEqual(
            {path: hashlib.sha256(path.read_bytes()).digest() for path in before_hashes},
            before_hashes,
        )

        connection = sqlite3.connect(account_db)
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT account_email, user_id FROM identity_mappings"
                ).fetchall(),
                [("shopper@example.com", "USR-TEST")],
            )
        finally:
            connection.close()

        connection = sqlite3.connect(shopping_db)
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                3,
            )
        finally:
            connection.close()

    def test_rejects_invalid_registration_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "valid email"):
            register_account("not-an-email", "correct-horse", "Demo Shopper")
        with self.assertRaisesRegex(ValueError, "between 12"):
            register_account("new@example.com", "short", "Demo Shopper")
        with self.assertRaisesRegex(ValueError, "Enter your name"):
            register_account("new@example.com", "correct-horse", " ")

    def test_account_schema_validation_uses_an_isolated_database(self) -> None:
        _shopping_db, account_db = create_shopwise_databases(self)
        with patch("app.db.schema._account_database_path", return_value=account_db):
            validate_account_schema()
        connection = sqlite3.connect(account_db)
        try:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(accounts)")
            }
        finally:
            connection.close()
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
