from __future__ import annotations

import datetime as dt
import os
import time
import xml.etree.ElementTree as ET
from typing import Iterable

from database import ensure_db, get_connection
from models import Job, Source


DEFAULT_FEED_PATH = os.path.join(os.path.dirname(__file__), "sample_data", "sample_jobs.xml")


def init_db() -> None:
    ensure_db()
    with get_connection() as conn:
        cur = conn.execute("SELECT id FROM sources WHERE name = ?", ("Demo RSS",))
        if cur.fetchone() is None:
            conn.execute(
                "INSERT INTO sources (name, type, feed_url, enabled) VALUES (?, ?, ?, ?)",
                ("Demo RSS", "rss", os.getenv("DEMO_FEED_URL", DEFAULT_FEED_PATH), 1),
            )


def load_feed(source: Source) -> Iterable[ET.Element]:
    feed_url = source.feed_url
    tree = ET.parse(feed_url)
    return tree.findall(".//item")


def _entry_to_job(entry: ET.Element, source: Source) -> Job:
    def text_or_default(tag: str, default: str) -> str:
        element = entry.find(tag)
        return (element.text or default).strip() if element is not None else default

    title = text_or_default("title", "Untitled role")
    company = text_or_default("author", "Unknown company")
    location = text_or_default("category", "Remote")
    description = text_or_default("description", "")
    source_url = text_or_default("link", "")
    posted_at = text_or_default("pubDate", dt.datetime.utcnow().isoformat())
    try:
        posted_struct = time.strptime(posted_at, "%a, %d %b %Y %H:%M:%S %Z")
        posted_iso = dt.datetime.fromtimestamp(time.mktime(posted_struct)).isoformat()
    except Exception:
        posted_iso = dt.datetime.utcnow().isoformat()

    normalized_hash = Job.compute_hash(title, company, location, source_url)
    return Job(
        id=None,
        title=title,
        company=company,
        location=location or "Remote",
        description=description,
        source_url=source_url,
        source_name=source.name,
        posted_at=posted_iso,
        ingested_at=Job.now_iso(),
        normalized_hash=normalized_hash,
    )


def upsert_jobs(entries: Iterable[ET.Element], source: Source) -> int:
    created = 0
    with get_connection() as conn:
        for entry in entries:
            job = _entry_to_job(entry, source)
            existing = conn.execute("SELECT id FROM jobs WHERE normalized_hash = ?", (job.normalized_hash,)).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE jobs
                    SET title = ?, company = ?, location = ?, description = ?, source_url = ?,
                        source_name = ?, posted_at = ?, ingested_at = ?
                    WHERE normalized_hash = ?
                    """,
                    (
                        job.title,
                        job.company,
                        job.location,
                        job.description,
                        job.source_url,
                        job.source_name,
                        job.posted_at,
                        job.ingested_at,
                        job.normalized_hash,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO jobs (title, company, location, description, source_url, source_name, posted_at, ingested_at, normalized_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.title,
                        job.company,
                        job.location,
                        job.description,
                        job.source_url,
                        job.source_name,
                        job.posted_at,
                        job.ingested_at,
                        job.normalized_hash,
                    ),
                )
                created += 1
        conn.execute(
            "UPDATE sources SET last_run_at = ? WHERE name = ?",
            (dt.datetime.utcnow().isoformat(), source.name),
        )
    return created


def ingest_sources() -> int:
    init_db()
    total_created = 0
    with get_connection() as conn:
        rows = conn.execute("SELECT id, name, type, feed_url, enabled, last_run_at FROM sources WHERE enabled = 1").fetchall()
    for row in rows:
        source = Source(
            id=row[0],
            name=row[1],
            type=row[2],
            feed_url=row[3],
            enabled=bool(row[4]),
            last_run_at=row[5],
        )
        entries = load_feed(source)
        total_created += upsert_jobs(entries, source)
    return total_created


if __name__ == "__main__":
    inserted = ingest_sources()
    print(f"Ingestion finished. New jobs created: {inserted}")
