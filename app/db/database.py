from pathlib import Path
import sqlite3

# Project root = agentic-ai-project/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "shopping.db"


def get_connection() -> sqlite3.Connection:
    """Create a connection to the local SQLite database."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    database_uri = f"{DB_PATH.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(database_uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def get_writable_connection() -> sqlite3.Connection:
    """Create a connection for explicitly owned writable shopping operations."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
