import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.authentication import authenticate_account, register_account


class AccountAuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "accounts.sqlite3"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

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


if __name__ == "__main__":
    unittest.main()
