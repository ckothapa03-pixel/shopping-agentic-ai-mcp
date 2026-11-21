import hashlib
import hmac
import logging
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, TypedDict

from app.db.identity import resolve_shopping_user
from app.db.database import connect_writable
from app.shopping.login_protection import (
    clear_login_failures,
    login_allowed,
    record_login_failure,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PASSWORD_ITERATIONS = 600_000
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 1024
_DUMMY_PASSWORD_SALT = b"shopwise-invalid-account-salt"
_AUTH_LOG = logging.getLogger("app.authentication")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Account(TypedDict):
    email: str
    full_name: str
    user_id: str


def _database_path(db_path: Path | str | None) -> Path:
    return Path(
        db_path
        or os.environ.get("SHOPPING_AUTH_DB")
        or PROJECT_ROOT / "accounts.sqlite3"
    )


def _connect(db_path: Path | str | None) -> sqlite3.Connection:
    path = _database_path(db_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"Account database not found: {path}. Provide an existing accounts.sqlite3 database."
        )
    return connect_writable(path)


@contextmanager
def _account_connection(
    db_path: Path | str | None,
) -> Generator[sqlite3.Connection, None, None]:
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
    if not isinstance(password, str) or not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH} characters."
        )
    return normalized_email, password


def register_account(
    email: str,
    password: str,
    full_name: str,
    db_path: Path | str | None = None,
    shopping_db_path: Path | str | None = None,
) -> Account:
    normalized_email, password = _validated_credentials(email, password)
    if not isinstance(full_name, str) or not full_name.strip():
        raise ValueError("Enter your name.")

    shopping_user = resolve_shopping_user(
        normalized_email,
        db_path=shopping_db_path,
        account_db_path=db_path,
    )
    if shopping_user is None:
        raise ValueError(
            "This email is not linked to an active Shopwise shopping profile."
        )

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
    _AUTH_LOG.info("event=account_registered")
    return {
        "email": normalized_email,
        "full_name": full_name.strip(),
        "user_id": shopping_user["user_id"],
    }


def authenticate_account(
    email: str,
    password: str,
    db_path: Path | str | None = None,
    shopping_db_path: Path | str | None = None,
) -> Account | None:
    if not isinstance(email, str) or not isinstance(password, str):
        _AUTH_LOG.warning("event=login_failed reason=invalid_input")
        return None
    normalized_email = email.strip().lower()
    if not login_allowed(normalized_email):
        _AUTH_LOG.warning("event=login_failed reason=throttled")
        return None
    if len(password) > MAX_PASSWORD_LENGTH:
        record_login_failure(normalized_email)
        _AUTH_LOG.warning("event=login_failed reason=invalid_credentials")
        return None
    if not EMAIL_PATTERN.fullmatch(normalized_email):
        record_login_failure(normalized_email)
        _AUTH_LOG.warning("event=login_failed reason=invalid_credentials")
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
        hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _DUMMY_PASSWORD_SALT, PASSWORD_ITERATIONS
        )
        record_login_failure(normalized_email)
        _AUTH_LOG.warning("event=login_failed reason=invalid_credentials")
        return None

    candidate_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        account["password_salt"],
        PASSWORD_ITERATIONS,
    )
    if not hmac.compare_digest(candidate_hash, account["password_hash"]):
        record_login_failure(normalized_email)
        _AUTH_LOG.warning("event=login_failed reason=invalid_credentials")
        return None

    shopping_user = resolve_shopping_user(
        normalized_email,
        db_path=shopping_db_path,
        account_db_path=db_path,
    )
    if shopping_user is None:
        record_login_failure(normalized_email)
        _AUTH_LOG.warning("event=login_failed reason=invalid_credentials")
        return None

    clear_login_failures(normalized_email)
    _AUTH_LOG.info("event=login_succeeded")

    return {
        "email": account["email"],
        "full_name": account["full_name"],
        "user_id": shopping_user["user_id"],
    }


def get_account_profile(
    email: str,
    db_path: Path | str | None = None,
    shopping_db_path: Path | str | None = None,
) -> Account | None:
    """Return only the account fields and canonical user ID for a profile."""
    if not isinstance(email, str):
        return None
    normalized_email = email.strip().lower()

    with _account_connection(db_path) as connection:
        account = connection.execute(
            """
            SELECT email, full_name
            FROM accounts
            WHERE email = ?
            """,
            (normalized_email,),
        ).fetchone()
    if account is None:
        return None

    shopping_user = resolve_shopping_user(
        normalized_email,
        db_path=shopping_db_path,
        account_db_path=db_path,
    )
    if shopping_user is None:
        return None

    return {
        "email": account["email"],
        "full_name": account["full_name"],
        "user_id": shopping_user["user_id"],
    }


def update_account_profile(
    email: str,
    full_name: str,
    db_path: Path | str | None = None,
    shopping_db_path: Path | str | None = None,
) -> Account:
    if not isinstance(full_name, str) or not full_name.strip():
        raise ValueError("Enter your name.")
    if not isinstance(email, str):
        raise ValueError("Enter a valid email address.")

    normalized_email = email.strip().lower()
    shopping_user = resolve_shopping_user(
        normalized_email,
        db_path=shopping_db_path,
        account_db_path=db_path,
    )
    if shopping_user is None:
        raise ValueError("This account is not linked to an active shopping profile.")

    with _account_connection(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE accounts
            SET full_name = ?
            WHERE email = ?
            """,
            (full_name.strip(), normalized_email),
        )
        if cursor.rowcount != 1:
            raise ValueError("Account was not found.")
    _AUTH_LOG.info("event=password_changed")

    return {
        "email": normalized_email,
        "full_name": full_name.strip(),
        "user_id": shopping_user["user_id"],
    }


def change_account_password(
    email: str,
    current_password: str,
    new_password: str,
    db_path: Path | str | None = None,
) -> None:
    if not isinstance(email, str) or not isinstance(current_password, str):
        raise ValueError("Enter your current email and password.")
    normalized_email = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized_email):
        raise ValueError("Enter a valid email address.")
    if not isinstance(new_password, str) or not MIN_PASSWORD_LENGTH <= len(new_password) <= MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"New password must be between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH} characters."
        )

    with _account_connection(db_path) as connection:
        account = connection.execute(
            """
            SELECT password_salt, password_hash
            FROM accounts
            WHERE email = ?
            """,
            (normalized_email,),
        ).fetchone()
        if account is None:
            raise ValueError("Current password is incorrect.")

        candidate_hash = hashlib.pbkdf2_hmac(
            "sha256",
            current_password.encode("utf-8"),
            account["password_salt"],
            PASSWORD_ITERATIONS,
        )
        if not hmac.compare_digest(candidate_hash, account["password_hash"]):
            raise ValueError("Current password is incorrect.")

        if hmac.compare_digest(candidate_hash, account["password_hash"]):
            if hmac.compare_digest(
                candidate_hash,
                hashlib.pbkdf2_hmac(
                    "sha256",
                    new_password.encode("utf-8"),
                    account["password_salt"],
                    PASSWORD_ITERATIONS,
                ),
            ):
                raise ValueError("New password must be different from the current password.")

        salt = secrets.token_bytes(16)
        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            new_password.encode("utf-8"),
            salt,
            PASSWORD_ITERATIONS,
        )
        cursor = connection.execute(
            """
            UPDATE accounts
            SET password_salt = ?, password_hash = ?
            WHERE email = ?
            """,
            (salt, password_hash, normalized_email),
        )
        if cursor.rowcount != 1:
            raise ValueError("Account was not found.")
