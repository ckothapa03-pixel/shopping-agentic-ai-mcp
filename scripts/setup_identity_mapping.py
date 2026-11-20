"""Provision the existing Shopwise account and its dedicated identity mapping."""

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SHOPPING_DB = PROJECT_ROOT / "shopping.db"
ACCOUNT_DB = PROJECT_ROOT / "accounts.sqlite3"
ACCOUNT_EMAIL = "ckothapa03@gmail.com"
NEW_USER_ID = "ckothapa03"
NEW_USER_NAME = "chaitu"


def main() -> None:
    if not SHOPPING_DB.is_file():
        raise FileNotFoundError(SHOPPING_DB)
    if not ACCOUNT_DB.is_file():
        raise FileNotFoundError(ACCOUNT_DB)

    shopping = sqlite3.connect(SHOPPING_DB, timeout=30)
    accounts = sqlite3.connect(ACCOUNT_DB, timeout=30)
    shopping.row_factory = sqlite3.Row
    accounts.row_factory = sqlite3.Row
    try:
        account = accounts.execute(
            "SELECT email, full_name FROM accounts WHERE LOWER(email) = LOWER(?)",
            (ACCOUNT_EMAIL,),
        ).fetchone()
        if account is None:
            raise RuntimeError("Approved account was not found.")

        shopping.execute("BEGIN IMMEDIATE")
        accounts.execute("BEGIN IMMEDIATE")

        existing_user = shopping.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (NEW_USER_ID,),
        ).fetchone()
        if existing_user is not None:
            raise RuntimeError("The proposed new shopping user ID already exists.")

        existing_email = shopping.execute(
            "SELECT user_id FROM users WHERE LOWER(email) = LOWER(?)",
            (ACCOUNT_EMAIL,),
        ).fetchone()
        if existing_email is not None:
            raise RuntimeError("A shopping user already owns this email.")

        accounts.execute(
            """
            CREATE TABLE IF NOT EXISTS identity_mappings (
                account_email TEXT PRIMARY KEY,
                user_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        existing_mapping = accounts.execute(
            "SELECT user_id FROM identity_mappings WHERE LOWER(account_email) = LOWER(?)",
            (ACCOUNT_EMAIL,),
        ).fetchone()
        if existing_mapping is not None:
            raise RuntimeError("This account already has an identity mapping.")

        shopping.execute(
            """
            INSERT INTO users
                (user_id, full_name, email, phone, created_at, is_active)
            VALUES (?, ?, ?, NULL, CURRENT_TIMESTAMP, 1)
            """,
            (
                NEW_USER_ID,
                account["full_name"] or NEW_USER_NAME,
                ACCOUNT_EMAIL,
            ),
        )

        accounts.execute(
            """
            INSERT INTO identity_mappings (account_email, user_id)
            VALUES (?, ?)
            """,
            (ACCOUNT_EMAIL.lower(), NEW_USER_ID),
        )

        shopping.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_nocase "
            "ON users (LOWER(email))"
        )

        shopping.commit()
        accounts.commit()
    except Exception:
        try:
            shopping.rollback()
        finally:
            try:
                accounts.rollback()
            finally:
                raise
    finally:
        shopping.close()
        accounts.close()


if __name__ == "__main__":
    main()
