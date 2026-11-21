from pathlib import Path
import os
import sqlite3

# Project root = agentic-ai-project/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(
    os.environ.get("SHOPWISE_DB_PATH") or PROJECT_ROOT / "shopping.db"
).expanduser().resolve()
SQLITE_BUSY_TIMEOUT_MS = 5000


def _configure_connection(connection: sqlite3.Connection) -> sqlite3.Connection:
    connection.row_factory = sqlite3.Row
    connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def connect_readonly(path: Path) -> sqlite3.Connection:
    """Open an existing database in read-only mode with bounded lock waiting."""
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Database not found: {path}")
    uri = f"{path.as_uri()}?mode=ro"
    connection = sqlite3.connect(
        uri,
        uri=True,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
    )
    return _configure_connection(connection)


def connect_writable(path: Path) -> sqlite3.Connection:
    """Open an existing database for writes without allowing implicit creation."""
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Database not found: {path}")
    uri = f"{path.as_uri()}?mode=rw"
    connection = sqlite3.connect(
        uri,
        uri=True,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
    )
    return _configure_connection(connection)


def get_connection() -> sqlite3.Connection:
    """Create a connection to the local SQLite database."""
    return connect_readonly(DB_PATH)


def get_writable_connection() -> sqlite3.Connection:
    """Create a connection for explicitly owned writable shopping operations."""
    return connect_writable(DB_PATH)
