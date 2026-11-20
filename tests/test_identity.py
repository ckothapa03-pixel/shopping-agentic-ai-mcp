import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.db.identity import (
    resolve_shopping_user,
    resolve_shopping_user_by_id,
)
from app.shopping.authentication import (
    authenticate_account,
    change_account_password,
    get_account_profile,
    register_account,
    update_account_profile,
)
from app.shopping.identity import (
    ensure_resource_owner,
    require_authenticated_user,
)


class IdentityFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        root = Path(temporary_directory.name)
        self.shopping_db = root / "shopping.db"
        self.account_db = root / "accounts.sqlite3"

        shopping_connection = sqlite3.connect(self.shopping_db)
        try:
            connection = shopping_connection
            connection.execute(
                """
                CREATE TABLE users (
                    user_id TEXT PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT,
                    created_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            connection.execute(
                """
                INSERT INTO users
                    (user_id, full_name, email, created_at, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "USR-100",
                    "Existing Shopper",
                    "shopper@example.com",
                    "2026-01-01",
                    1,
                ),
            )
            connection.execute(
                """
                INSERT INTO users
                    (user_id, full_name, email, created_at, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "USR-INACTIVE",
                    "Inactive Shopper",
                    "inactive@example.com",
                    "2026-01-01",
                    0,
                ),
            )
        finally:
            shopping_connection.commit()
            shopping_connection.close()

        account_connection = sqlite3.connect(self.account_db)
        try:
            connection = account_connection
            connection.execute(
                """
                CREATE TABLE accounts (
                    email TEXT PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE identity_mappings (
                    account_email TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        finally:
            account_connection.commit()
            account_connection.close()

    def test_email_resolves_exactly_one_active_shopping_user(self) -> None:
        account_connection = sqlite3.connect(self.account_db)
        try:
            account_connection.execute(
                """
                INSERT INTO identity_mappings (account_email, user_id)
                VALUES (?, ?)
                """,
                ("shopper@example.com", "USR-100"),
            )
            account_connection.commit()
        finally:
            account_connection.close()
        user = resolve_shopping_user(
            "SHOPPER@example.com",
            db_path=self.shopping_db,
            account_db_path=self.account_db,
        )
        self.assertEqual(user["user_id"], "USR-100")
        self.assertEqual(
            resolve_shopping_user_by_id(
                "USR-100",
                db_path=self.shopping_db,
            )["email"],
            "shopper@example.com",
        )
        self.assertIsNone(
            resolve_shopping_user(
                "unknown@example.com",
                db_path=self.shopping_db,
                account_db_path=self.account_db,
            )
        )
        self.assertIsNone(
            resolve_shopping_user(
                "inactive@example.com",
                db_path=self.shopping_db,
                account_db_path=self.account_db,
            )
        )

    def test_registration_authentication_profile_and_password_use_isolated_dbs(
        self,
    ) -> None:
        account_connection = sqlite3.connect(self.account_db)
        try:
            account_connection.execute(
                """
                INSERT INTO identity_mappings (account_email, user_id)
                VALUES (?, ?)
                """,
                ("shopper@example.com", "USR-100"),
            )
            account_connection.commit()
        finally:
            account_connection.close()
        account = register_account(
            "Shopper@example.com",
            "correct-horse",
            "Demo Shopper",
            db_path=self.account_db,
            shopping_db_path=self.shopping_db,
        )
        self.assertEqual(account["user_id"], "USR-100")

        authenticated = authenticate_account(
            "SHOPPER@example.com",
            "correct-horse",
            db_path=self.account_db,
            shopping_db_path=self.shopping_db,
        )
        self.assertEqual(authenticated["user_id"], "USR-100")
        self.assertIsNone(
            authenticate_account(
                "shopper@example.com",
                "wrong-password",
                db_path=self.account_db,
                shopping_db_path=self.shopping_db,
            )
        )

        profile = get_account_profile(
            "shopper@example.com",
            db_path=self.account_db,
            shopping_db_path=self.shopping_db,
        )
        self.assertEqual(profile["full_name"], "Demo Shopper")

        updated = update_account_profile(
            "shopper@example.com",
            "Updated Shopper",
            db_path=self.account_db,
            shopping_db_path=self.shopping_db,
        )
        self.assertEqual(updated["full_name"], "Updated Shopper")

        change_account_password(
            "shopper@example.com",
            "correct-horse",
            "new-correct-horse",
            db_path=self.account_db,
        )
        self.assertIsNone(
            authenticate_account(
                "shopper@example.com",
                "correct-horse",
                db_path=self.account_db,
                shopping_db_path=self.shopping_db,
            )
        )
        authenticated = authenticate_account(
            "shopper@example.com",
            "new-correct-horse",
            db_path=self.account_db,
            shopping_db_path=self.shopping_db,
        )
        self.assertEqual(authenticated["user_id"], "USR-100")

    def test_registration_rejects_unlinked_and_inactive_profiles(self) -> None:
        with self.assertRaisesRegex(ValueError, "not linked"):
            register_account(
                "unknown@example.com",
                "correct-horse",
                "Unknown Shopper",
                db_path=self.account_db,
                shopping_db_path=self.shopping_db,
            )
        with self.assertRaisesRegex(ValueError, "not linked"):
            register_account(
                "inactive@example.com",
                "correct-horse",
                "Inactive Shopper",
                db_path=self.account_db,
                shopping_db_path=self.shopping_db,
            )

    def test_authorization_helpers_require_canonical_ownership(self) -> None:
        guest = {"access_mode": "guest"}
        with self.assertRaises(PermissionError):
            require_authenticated_user(guest)

        authenticated = {
            "access_mode": "authenticated",
            "authenticated_user_id": "USR-100",
        }
        self.assertEqual(require_authenticated_user(authenticated), "USR-100")

        ensure_resource_owner("USR-100", "USR-100")
        with self.assertRaises(PermissionError):
            ensure_resource_owner("USR-200", "USR-100")


if __name__ == "__main__":
    unittest.main()
