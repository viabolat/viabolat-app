from __future__ import annotations

import importlib
import pytest


def reload_modules():
    import database
    import ingestion

    importlib.reload(database)
    importlib.reload(ingestion)
    return database, ingestion


@pytest.fixture()
def temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", str(db_path))
    database, ingestion = reload_modules()
    return db_path, database, ingestion


def test_ingestion_creates_and_deduplicates_jobs(temp_db):
    db_path, database, ingestion = temp_db

    ingestion.init_db()
    first_created = ingestion.ingest_sources()
    second_created = ingestion.ingest_sources()

    with database.get_connection(str(db_path)) as conn:
        job_count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    assert first_created > 0, "First ingest should create demo jobs"
    assert second_created == 0, "Second ingest should deduplicate existing jobs"
    assert job_count == first_created, "Job table should not grow after dedupe"


def test_ingestion_handles_missing_feed_gracefully(temp_db):
    db_path, database, ingestion = temp_db

    ingestion.init_db()
    with database.get_connection(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO sources (name, type, feed_url, enabled) VALUES (?, ?, ?, ?)",
            ("Broken", "rss", "/nonexistent/path.xml", 1),
        )

    created = ingestion.ingest_sources()

    with database.get_connection(str(db_path)) as conn:
        job_count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    assert created > 0, "Healthy source should still ingest jobs"
    assert job_count == created, "Jobs table should only include successful ingests"
