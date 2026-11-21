import os
from contextlib import closing
from pathlib import Path
from typing import TypedDict

from app.db.database import DB_PATH, connect_readonly


def _account_database_path() -> Path:
    configured = os.environ.get("SHOPPING_AUTH_DB")
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parents[2] / "accounts.sqlite3"


class ShoppingUser(TypedDict):
    user_id: str
    full_name: str
    email: str
    is_active: bool


def resolve_shopping_user(
    email: str,
    db_path: Path | str | None = None,
    account_db_path: Path | str | None = None,
) -> ShoppingUser | None:
    """Resolve an account email to exactly one active shopping user."""
    if not isinstance(email, str) or not email.strip():
        return None

    path = Path(db_path or DB_PATH).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Database not found: {path}")

    account_path = (
        Path(account_db_path).resolve()
        if account_db_path is not None
        else _account_database_path()
    )
    if not account_path.is_file():
        raise FileNotFoundError(f"Account database not found: {account_path}")

    with closing(connect_readonly(path)) as connection:
        with closing(connect_readonly(account_path)) as account_connection:
            mapping = account_connection.execute(
                """
                SELECT account_email, user_id
                FROM identity_mappings
                WHERE LOWER(account_email) = LOWER(?)
                """,
                (email.strip(),),
            ).fetchone()
            if mapping is None:
                return None
            user_id = str(mapping["user_id"])

        row = connection.execute(
            """
            SELECT user_id, full_name, email, is_active
            FROM users
            WHERE user_id = ?
              AND is_active = 1
            """,
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "user_id": str(row["user_id"]),
        "full_name": str(row["full_name"]),
        "email": str(row["email"]),
        "is_active": bool(row["is_active"]),
    }


def resolve_shopping_user_by_id(
    user_id: str,
    db_path: Path | str | None = None,
) -> ShoppingUser | None:
    """Resolve a canonical shopping user ID without exposing private fields."""
    if not isinstance(user_id, str) or not user_id.strip():
        return None

    path = Path(db_path or DB_PATH).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Database not found: {path}")

    with closing(connect_readonly(path)) as connection:
        row = connection.execute(
            """
            SELECT user_id, full_name, email, is_active
            FROM users
            WHERE user_id = ?
              AND is_active = 1
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        return None
    return {
        "user_id": str(row["user_id"]),
        "full_name": str(row["full_name"]),
        "email": str(row["email"]),
        "is_active": bool(row["is_active"]),
    }
