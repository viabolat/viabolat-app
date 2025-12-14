# Viabolat Job Feed Demo

A minimal Flask prototype that ingests RSS job feeds into SQLite and exposes them via HTML and JSON endpoints. Use it to preview the job-aggregation experience locally before connecting real sources.

## Quick start (local)
1. **Install dependencies** (Python 3.11+):
   ```bash
   python -m pip install -r requirements.txt
   ```
2. **Optional environment**
   - `DATABASE_URL`: path to the SQLite file (default: `viabolat.db`).
   - `DEMO_FEED_URL`: override the bundled `sample_data/sample_jobs.xml` feed.
   - `BOOTSTRAP`: set to `false` to skip ingestion on every app start once the DB is warm.
3. **Ingest demo data** (creates tables and loads the demo feed):
   ```bash
   python ingestion.py
   ```
4. **Run the web app** (defaults to port 5000):
   ```bash
   python app.py
   ```
   Visit `http://localhost:5000/` for the landing page, `/jobs` for the full list, or `/api/jobs` for JSON.

## Running tests
```bash
python -m pytest
```

## Deploying a live preview (Render)
Render uses `render.yaml` to start the app with `python app.py`. Ensure your environment variables (e.g., `DATABASE_URL`, `DEMO_FEED_URL`) are set in the Render dashboard and that `BOOTSTRAP` is `true` on first deploy to seed data.
