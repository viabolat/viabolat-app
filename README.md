# Viabolat Job Feed Demo

A minimal Flask prototype that ingests RSS job feeds into SQLite and exposes them via HTML and JSON endpoints. Use it to preview the job-aggregation experience locally before connecting real sources. The steps below now include a production-friendly container image, a WSGI entrypoint, and health checks.

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

## Production-style run (Gunicorn)
- Build/run via Docker:
  ```bash
  docker build -t viabolat-app .
  docker run -p 8000:8000 --env-file .env.example viabolat-app
  ```
- Direct run without Docker:
  ```bash
  python -m pip install -r requirements.txt
  gunicorn wsgi:app --bind 0.0.0.0:8000 --workers 2 --timeout 60
  ```
- Health check: `GET /healthz` returns `{"status": "ok"}` when the app and database are reachable.

## Scheduling ingestion for live use
- Run `python ingestion.py` on a schedule (e.g., cron every 30 minutes or a managed scheduler) to keep feeds fresh.
- Set `BOOTSTRAP=false` for the web process once data is seeded; keep the ingestion worker separate from the web workers.
- Use `DEMO_FEED_URL` (or real feed URLs in the `sources` table) to point at live sources.

## Running tests
```bash
python -m pytest
```

## Deploying a live preview (Render)
Render uses `render.yaml` to start the app with Gunicorn. Suggested settings:
- Start command (already in `render.yaml`): `gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --timeout 60`
- Add a Render Cron Job to run `python ingestion.py` every 30 minutes.
- Set `BOOTSTRAP=true` on first deploy if you want the web container to seed once; afterwards set `BOOTSTRAP=false` and rely on the cron job.
- Configure `DATABASE_URL` (e.g., Render Disk path or managed Postgres if you swap databases) and any feed URLs in the Render dashboard.
