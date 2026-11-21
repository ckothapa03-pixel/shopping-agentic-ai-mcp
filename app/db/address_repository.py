from contextlib import closing
from typing import Any

from app.db.database import get_connection, get_writable_connection
from app.db.user_data import ensure_active_user


def list_addresses(user_id: str) -> list[dict[str, Any]]:
    ensure_active_user(user_id)
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT id, user_id, label, line1, city, state, pincode, is_default
            FROM addresses
            WHERE user_id=? ORDER BY is_default DESC, id
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_address(user_id: str, address_id: int) -> dict[str, Any] | None:
    ensure_active_user(user_id)
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT id, user_id, label, line1, city, state, pincode, is_default
            FROM addresses
            WHERE id=? AND user_id=?
            """,
            (address_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def _validate_address(label: str, line1: str, city: str, state: str, pincode: str) -> None:
    for value, name in ((label, "Label"), (line1, "Address"), (city, "City"), (state, "State"), (pincode, "Pincode")):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} is required")
    if not pincode.strip().replace(" ", "").isdigit():
        raise ValueError("Pincode must contain digits")


def create_address(user_id: str, label: str, line1: str, city: str, state: str, pincode: str, is_default: bool = False) -> dict[str, Any]:
    ensure_active_user(user_id)
    _validate_address(label, line1, city, state, pincode)
    with closing(get_writable_connection()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        if is_default:
            connection.execute("UPDATE addresses SET is_default=0 WHERE user_id=?", (user_id,))
        elif connection.execute("SELECT COUNT(*) FROM addresses WHERE user_id=?", (user_id,)).fetchone()[0] == 0:
            is_default = True
        cursor = connection.execute(
            """
            INSERT INTO addresses (user_id,label,line1,city,state,pincode,is_default)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, label.strip(), line1.strip(), city.strip(), state.strip(), pincode.strip(), int(is_default)),
        )
        connection.commit()
    return get_address(user_id, int(cursor.lastrowid))


def update_address(user_id: str, address_id: int, label: str, line1: str, city: str, state: str, pincode: str, is_default: bool = False) -> dict[str, Any]:
    ensure_active_user(user_id)
    _validate_address(label, line1, city, state, pincode)
    with closing(get_writable_connection()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT id FROM addresses WHERE id=? AND user_id=?",
            (address_id, user_id),
        ).fetchone()
        if existing is None:
            raise PermissionError("Address not found.")
        if is_default:
            connection.execute("UPDATE addresses SET is_default=0 WHERE user_id=?", (user_id,))
        connection.execute(
            """
            UPDATE addresses
            SET label=?, line1=?, city=?, state=?, pincode=?, is_default=?
            WHERE id=? AND user_id=?
            """,
            (label.strip(), line1.strip(), city.strip(), state.strip(), pincode.strip(), int(is_default), address_id, user_id),
        )
        connection.commit()
    return get_address(user_id, address_id)


def delete_address(user_id: str, address_id: int) -> None:
    ensure_active_user(user_id)
    with closing(get_writable_connection()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT is_default FROM addresses WHERE id=? AND user_id=?",
            (address_id, user_id),
        ).fetchone()
        if row is None:
            raise PermissionError("Address not found.")
        connection.execute("DELETE FROM addresses WHERE id=? AND user_id=?", (address_id, user_id))
        if row["is_default"]:
            replacement = connection.execute(
                "SELECT id FROM addresses WHERE user_id=? ORDER BY id LIMIT 1",
                (user_id,),
            ).fetchone()
            if replacement:
                connection.execute(
                    "UPDATE addresses SET is_default=1 WHERE id=? AND user_id=?",
                    (replacement["id"], user_id),
                )
        connection.commit()
