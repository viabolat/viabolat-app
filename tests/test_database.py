from __future__ import annotations

from pathlib import Path

import database


def test_get_connection_accepts_override_path(tmp_path):
    override = tmp_path / "custom" / "db.sqlite"

    with database.get_connection(override) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS sample (id INTEGER PRIMARY KEY)")

    assert override.exists(), "Database file should be created at the overridden path"
    with database.get_connection(override) as conn:
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sample'").fetchone()
        assert row is not None, "Table should persist when reopening connection"
