import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TypedDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PASSWORD_ITERATIONS = 600_000
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Account(TypedDict):
    email: str
    full_name: str


def _database_path(db_path: Path | str | None) -> Path:
    return Path(
        db_path
        or os.environ.get("SHOPPING_AUTH_DB")
        or PROJECT_ROOT / "accounts.sqlite3"
    )


def _connect(db_path: Path | str | None) -> sqlite3.Connection:
    path = _database_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            email TEXT PRIMARY KEY COLLATE NOCASE,
            full_name TEXT NOT NULL,
            password_salt BLOB NOT NULL,
            password_hash BLOB NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return connection


@contextmanager
def _account_connection(
    db_path: Path | str | None,
) -> Iterator[sqlite3.Connection]:
    connection = _connect(db_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _validated_credentials(email: str, password: str) -> tuple[str, str]:
    if not isinstance(email, str):
        raise ValueError("Enter a valid email address.")
    normalized_email = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized_email):
        raise ValueError("Enter a valid email address.")
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    return normalized_email, password


def register_account(
    email: str,
    password: str,
    full_name: str,
    db_path: Path | str | None = None,
) -> Account:
    normalized_email, password = _validated_credentials(email, password)
    if not isinstance(full_name, str) or not full_name.strip():
        raise ValueError("Enter your name.")

    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    try:
        with _account_connection(db_path) as connection:
            connection.execute(
                """
                INSERT INTO accounts (email, full_name, password_salt, password_hash)
                VALUES (?, ?, ?, ?)
                """,
                (normalized_email, full_name.strip(), salt, password_hash),
            )
    except sqlite3.IntegrityError as error:
        raise ValueError("An account with that email already exists.") from error
    return {"email": normalized_email, "full_name": full_name.strip()}


def authenticate_account(
    email: str,
    password: str,
    db_path: Path | str | None = None,
) -> Account | None:
    if not isinstance(email, str) or not isinstance(password, str):
        return None
    normalized_email = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized_email):
        return None

    with _account_connection(db_path) as connection:
        account = connection.execute(
            """
            SELECT email, full_name, password_salt, password_hash
            FROM accounts
            WHERE email = ?
            """,
            (normalized_email,),
        ).fetchone()

    if account is None:
        return None

    candidate_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        account["password_salt"],
        PASSWORD_ITERATIONS,
    )
    if not hmac.compare_digest(candidate_hash, account["password_hash"]):
        return None
    return {"email": account["email"], "full_name": account["full_name"]}
