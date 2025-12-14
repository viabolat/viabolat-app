from __future__ import annotations

import logging
import os
from flask import Flask, jsonify, render_template

from database import get_connection
from ingestion import ingest_sources, init_db


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)


def bootstrap() -> None:
    init_db()
    ingest_sources()


@app.route("/")
def home():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, company, location, description, source_url, source_name, posted_at, ingested_at FROM jobs ORDER BY ingested_at DESC LIMIT 10"
        ).fetchall()
    jobs = [dict(row) for row in rows]
    return render_template("index.html", jobs=jobs)


@app.route("/jobs")
def jobs():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, company, location, description, source_url, source_name, posted_at, ingested_at FROM jobs ORDER BY ingested_at DESC"
        ).fetchall()
    jobs = [dict(row) for row in rows]
    return render_template("jobs.html", jobs=jobs)


@app.route("/api/jobs")
def api_jobs():
    with get_connection() as conn:
        jobs = conn.execute(
            "SELECT id, title, company, location, description, source_url, source_name, posted_at, ingested_at FROM jobs ORDER BY ingested_at DESC"
        ).fetchall()
    payload = [dict(row) for row in jobs]
    return jsonify(payload)


@app.route("/healthz")
def healthz():
    """Lightweight health probe for load balancers."""
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
    except Exception:
        return jsonify({"status": "unhealthy"}), 503
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    if os.getenv("BOOTSTRAP", "true").lower() == "true":
        bootstrap()
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
