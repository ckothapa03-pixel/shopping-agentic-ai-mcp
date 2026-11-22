import hashlib
import sqlite3
import unittest

from app.db.identity import (
    resolve_shopping_user,
    resolve_shopping_user_by_id,
)
from app.shopping.authentication import (
    PASSWORD_ITERATIONS,
    authenticate_account,
    change_account_password,
    get_account_profile,
    register_account,
    update_account_profile,
)
from app.shopping.identity import (
    clear_authenticated_session,
    enter_guest_session,
    ensure_resource_owner,
    prepare_login_session,
    require_authenticated_user,
)
from tests.database_fixture import isolated_database_path


class IdentityFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.shopping_db = isolated_database_path(self, suffix=".db")
        self.account_db = isolated_database_path(self)

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

    def test_provisioned_account_authentication_profile_and_password_use_isolated_dbs(
        self,
    ) -> None:
        salt = b"isolated-test-salt"
        password_hash = hashlib.pbkdf2_hmac(
            "sha256", b"correct-horse", salt, PASSWORD_ITERATIONS
        )
        account_connection = sqlite3.connect(self.account_db)
        try:
            account_connection.execute(
                """
                INSERT INTO identity_mappings (account_email, user_id)
                VALUES (?, ?)
                """,
                ("shopper@example.com", "USR-100"),
            )
            account_connection.execute(
                """
                INSERT INTO accounts (email, full_name, password_salt, password_hash)
                VALUES (?, ?, ?, ?)
                """,
                ("shopper@example.com", "Demo Shopper", salt, password_hash),
            )
            account_connection.commit()
        finally:
            account_connection.close()
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
        connection = sqlite3.connect(self.account_db)
        try:
            connection.execute(
                """
                INSERT INTO identity_mappings (account_email, user_id)
                VALUES (?, ?)
                """,
                ("shopper@example.com", "USR-100"),
            )
            connection.commit()
        finally:
            connection.close()

        messages = []
        for email in (
            "shopper@example.com",
            "unknown@example.com",
            "inactive@example.com",
        ):
            with self.assertRaises(ValueError) as error:
                register_account(
                    email,
                    "correct-horse",
                    "Demo Shopper",
                    db_path=self.account_db,
                    shopping_db_path=self.shopping_db,
                )
            messages.append(str(error.exception))
        self.assertEqual(len(set(messages)), 1)

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

    def test_logout_and_account_switch_clear_private_session_data(self) -> None:
        session = {
            "access_mode": "authenticated",
            "authenticated_email": "shopper@example.com",
            "authenticated_user_id": "USR-100",
            "cart": {7: 2},
            "wishlist": {8},
            "chat_messages": [{"role": "assistant", "content": "private"}],
            "agent_history": ["private"],
        }
        clear_authenticated_session(session)
        self.assertEqual(session["access_mode"], "guest")
        self.assertNotIn("authenticated_user_id", session)
        self.assertEqual(session["cart"], {})
        self.assertEqual(session["wishlist"], set())
        self.assertEqual(session["chat_messages"], [])
        self.assertEqual(session["agent_history"], [])

        session.update(
            access_mode="authenticated",
            authenticated_user_id="USR-100",
            cart={9: 1},
            wishlist={10},
        )
        prepare_login_session(session)
        self.assertNotIn("authenticated_user_id", session)
        self.assertNotIn("access_mode", session)
        self.assertEqual(session["cart"], {})
        self.assertEqual(session["wishlist"], set())

    def test_guest_login_transition_removes_stale_identity_but_keeps_guest_cart(self) -> None:
        session = {
            "access_mode": "guest",
            "authenticated_user_id": "USR-OLD",
            "cart": {3: 1},
            "wishlist": {4},
            "agent_history": ["guest context"],
        }
        prepare_login_session(session)
        self.assertNotIn("authenticated_user_id", session)
        self.assertEqual(session["cart"], {3: 1})
        self.assertEqual(session["wishlist"], {4})
        self.assertEqual(session["agent_history"], [])

        enter_guest_session(session)
        self.assertEqual(session["access_mode"], "guest")


if __name__ == "__main__":
    unittest.main()
