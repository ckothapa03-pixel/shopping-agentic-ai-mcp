-- Run this setup before starting Shopwise.
-- This matches the accounts table defined by app/shopping/authentication.py.
CREATE TABLE IF NOT EXISTS accounts (
    email TEXT PRIMARY KEY COLLATE NOCASE,
    full_name TEXT NOT NULL,
    password_salt BLOB NOT NULL,
    password_hash BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
