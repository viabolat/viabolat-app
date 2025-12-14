from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_ENV_KEY = "DATABASE_URL"


def get_db_path() -> str:
    """Return the configured database path, defaulting to a local SQLite file."""
    return os.getenv(DB_ENV_KEY, "viabolat.db")


def ensure_db(db_path: str | None = None) -> None:
    path = db_path or get_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with get_connection(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL,
                feed_url TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_run_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_name TEXT NOT NULL,
                posted_at TEXT NOT NULL,
                ingested_at TEXT NOT NULL,
                normalized_hash TEXT NOT NULL UNIQUE
            )
            """
        )


@contextmanager
def get_connection(db_path: str | os.PathLike[str] | None = None):
    """Yield a SQLite connection for the configured database path.

    Accepts an optional override path to support per-test or ad-hoc databases
    without mutating global configuration. Ensures the parent directory exists
    before opening the database file.
    """
    path = str(db_path or get_db_path())
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
