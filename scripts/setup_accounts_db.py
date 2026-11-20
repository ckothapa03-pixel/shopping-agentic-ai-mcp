"""Verify the existing Shopwise accounts database without modifying it."""

import os
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COLUMNS = {
    "email",
    "full_name",
    "password_salt",
    "password_hash",
    "created_at",
}


def main() -> None:
    database_path = Path(
        os.environ.get("SHOPPING_AUTH_DB") or PROJECT_ROOT / "accounts.sqlite3"
    ).resolve()
    if not database_path.is_file():
        raise FileNotFoundError(f"Existing accounts database not found: {database_path}")

    database_uri = f"{database_path.as_uri()}?mode=ro"
    with sqlite3.connect(database_uri, uri=True) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if "accounts" not in tables:
            raise RuntimeError(
                f"The existing accounts table was not found in: {database_path}"
            )
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(accounts)").fetchall()
        }
        if columns != EXPECTED_COLUMNS:
            raise RuntimeError(
                "The existing accounts table does not have the expected columns. "
                f"Found: {sorted(columns)}"
            )

    print(f"Verified existing accounts table in: {database_path}")


if __name__ == "__main__":
    main()
