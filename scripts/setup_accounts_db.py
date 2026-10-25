"""Create the Shopwise accounts table before launching the application."""

import os
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = Path(__file__).with_name("accounts_schema.sql")


def main() -> None:
    database_path = Path(
        os.environ.get("SHOPPING_AUTH_DB") or PROJECT_ROOT / "accounts.sqlite3"
    ).resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(accounts)").fetchall()
        }
        expected_columns = {
            "email",
            "full_name",
            "password_salt",
            "password_hash",
            "created_at",
        }
        if columns != expected_columns:
            raise RuntimeError(
                "The existing accounts table does not match the project schema. "
                "No existing table or data was changed."
            )

    print(f"Accounts table is ready in: {database_path}")


if __name__ == "__main__":
    main()
