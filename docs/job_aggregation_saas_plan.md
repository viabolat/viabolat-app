# Job Aggregation SaaS Plan

## 1) Clarifying Assumptions
- Geographic focus starts with US/Canada; international expansion later.
- Only public, legally scrapeable sources; prefer APIs/RSS/sitemaps when provided.
- Payments use Stripe; no marketplace payout complexity.
- Auth via email/password + OAuth (Google) without SSO requirements initially.
- Initial scale: tens of thousands of postings/day across hundreds of sources.

## 2) Technical Plan
- **Architecture diagram (ASCII)**
  - `Users/SEO Traffic -> Next.js SSR/ISR -> FastAPI -> Postgres + Redis`
  - `Admin -> Next.js -> FastAPI -> Postgres`
  - `Scheduler (Temporal/Quartz) -> Queue (Celery/RQ) -> Connector Workers`
  - `Connector Workers -> S3 (raw) -> Normalizer -> Deduper/Upserter -> Postgres/OpenSearch`
  - `Observability (OTel) -> Prometheus -> Grafana -> PagerDuty/Slack`
  - `Stripe Webhooks -> FastAPI Billing Handler -> Postgres subscriptions`
- **Architecture diagram (text)**
  - Browser/SEO pages & Web App (Next.js/React) ↔ Backend API (FastAPI) ↔ DB (Postgres + PostGIS) & Cache (Redis).
  - Ingestion Scheduler (Temporal/Quartz) → Task Queue (Celery/RQ + Redis) → Source Connectors (HTTP/Playwright/RSS/API) → Raw Storage (S3) → Normalizer (workers) → Deduper/Upserter → DB.
  - Alerts/Observability (OpenTelemetry → Prometheus/Grafana + PagerDuty). Admin UI connects to API for source controls.
- **Scraping approach by source type**
  - Static HTML: `requests` + `selectolax`/`lxml`, pagination via link discovery; respect robots.txt and rate limits.
  - JS-rendered: Playwright headless with stealth profile; snapshot DOM then parse; fall back to HTML-only where possible.
  - RSS/API: Preferred; use ETag/If-Modified-Since; schema mapping per source.
  - Sitemaps: Parse sitemap index → child sitemaps → job URLs; fetch detail pages with conditional GET.
  - Email feeds/webhooks (optional partners): Ingest via inbound webhook endpoint.
  - **Connector checklist**: robots.txt compliance → fetch with per-domain throttling → parse with source-specific selectors → yield normalized records → push raw HTML to S3 for regression fixtures.
  - **Pagination patterns covered**: numbered pages, `Load more` buttons (Playwright click + wait), infinite scroll (scroll + response intercept), next/prev links, sitemap traversal.
- **Queue/scheduler design & rate limiting**
  - Central scheduler (Temporal/Quartz) emits per-source jobs with cron or interval configs.
  - Queue (Celery/RQ) with worker pools tagged by connector type (html/js/rss) and concurrency caps.
  - Token-bucket rate limiters per domain; adaptive backoff on 429/5xx; global concurrency guard.
  - Dead-letter queue for poison messages with capped retries; periodic requeue job to drain DLQ after fixes.
  - Distributed locks per source to avoid double-runs; idempotent connector entrypoints keyed by `source_id + url`.
- **Normalization strategy**
  - Canonical fields: `source_id`, `source_type`, `title`, `company`, `locations` (structured), `description_html`, `description_text`, `employment_type`, `seniority`, `categories`, `skills`, `salary` (value/currency/range), `remote_policy`, `apply_url`, `posted_at`, `expires_at`, `collected_at`, `language`, `source_url`, `hashes`.
  - Parsing rules: strip tracking params, normalize whitespace, HTML sanitize, timezone-normalized dates, geo enrich via geocoder (PostGIS), salary parsing with currency detection.
  - Enrichment: company normalization via lookup table, inferred remote flag from keywords, language detection, keyword tagging, embedding vector optional for search.
  - Output contract enforced via Pydantic models; reject/flag records failing validation and send to QA queue.
- **Duplicate/change detection**
  - Dedup keys: stable `source_url` normalized + `apply_url`; fallback fingerprint from `title + company + location` hash.
  - Similarity check: MinHash/LSH on `description_text` to catch near-duplicates across sources.
  - Versioning: `content_hash` per fetch; if changed, create new revision row and update `updated_at`; maintain `history` table for diffs.
  - On conflict policy: upsert primary job row; append to `job_history`; flag breaking schema drift to admin queue.
- **Failure handling**
  - Timeouts per connector; retries with exponential backoff and jitter; max retry count before circuit breaker opens for that source.
  - Fallbacks: switch to lighter fetch (HTML → RSS if available); reduce concurrency when error rate spikes; capture snapshots to S3 for debugging.
  - Alerting on sustained error rate, repeated 403/429, schema drift, or empty result anomalies.
  - Graceful degradation: pause specific selectors when DOM shifts cause empty fields; auto-roll back to last good parser config.
  - Health scoring: rolling error rate + freshness; auto-disable and notify when below threshold.
- **Observability**
  - Structured logging with trace IDs; OpenTelemetry spans around fetch/parse/upsert.
  - Metrics: per-source success rate, latency, dedupe ratio, freshness (age of newest posting), queue depth, worker CPU/memory.
  - Dashboards in Grafana; alerts via PagerDuty/Slack on SLO breaches.
  - Log sampling for noisy sources; retain full logs on failures only; trace context propagated from scheduler to connectors to DB writes.
- **Security**
  - Auth: JWT sessions, RLS in Postgres for user data; OAuth with Google optional.
  - Payments: Stripe subscriptions + webhooks with signature validation; enforce paywall on search results depth and saved alerts.
  - Secrets in env/secret manager (not in repo); HTTPS everywhere; CSRF protection; rate-limit login/password reset; captcha on signup abuse.
  - PII handling: minimal storage (email, hashed passwords); audit logs for admin actions.
  - Abuse prevention: WAF rules for bots, IP allow/deny lists for admin, alerts on anomalous login velocity; limit export/CSV endpoints.
- **SEO foundations**
  - SSR for job detail and listing pages; canonical URLs; meta tags per job; JSON-LD JobPosting schema.
  - XML sitemaps auto-generated per taxonomy; fast LCP via edge caching/CDN; clean URLs with slugs.
  - Noindex on duplicate/filtered pages; robots.txt honoring; performance budget with image/script optimization.
  - Daily sitemap refresh with lastmod timestamps; hreflang for multi-language later; preload critical CSS; lazy-load maps and heavy widgets.

## 3) Data Model
- **Database**: Postgres + PostGIS for geo; Redis for cache/rate limits; S3 for raw snapshots; optional OpenSearch/Meilisearch for full-text.
- **Tables (key fields only)**
  - `sources(id, name, type, base_url, schedule, parser_config, rate_limit, status, last_run_at, failure_count, auth_config, compliance_notes)`
  - `raw_fetches(id, source_id, url, status, fetched_at, latency_ms, http_status, storage_key, content_hash, error)`
  - `jobs(id UUID, source_id, source_url, apply_url, title, company_id, company_name, description_html, description_text, employment_type, seniority, categories, skills, salary_min, salary_max, currency, remote_policy, location_geog, locations_text, posted_at, expires_at, language, content_hash, version, created_at, updated_at, is_active)`
  - `job_history(id, job_id, version, content_hash, diff, changed_at)`
  - `companies(id, name, website, normalized_name, linkedin, crunchbase_id)`
  - `users(id, email, password_hash, stripe_customer_id, role, created_at)`
  - `subscriptions(id, user_id, stripe_sub_id, status, plan, renews_at, canceled_at)`
  - `saved_jobs(id, user_id, job_id, created_at)`
  - `alerts(id, user_id, query, cadence, last_sent_at)`
  - Indexes: `jobs(source_url)`, `jobs(content_hash)`, GIN trigram on `title/description`, GiST on `location_geog`, composite on `(company_name, title, locations_text)`; partial index on `is_active=true`.
  - Partitioning: monthly partitions for `jobs`, `raw_fetches` for faster deletes; retention jobs drop cold partitions to archive.
- **Example normalized job record**
  ```json
  {
    "id": "uuid",
    "source_id": 12,
    "source_url": "https://board.example.com/jobs/123",
    "apply_url": "https://company.com/apply/123?ref=clean",
    "title": "Senior Data Engineer",
    "company_name": "Acme Corp",
    "description_text": "Build pipelines...",
    "employment_type": "full_time",
    "seniority": "senior",
    "categories": ["data", "engineering"],
    "skills": ["python", "spark", "airflow"],
    "salary_min": 160000,
    "salary_max": 190000,
    "currency": "USD",
    "remote_policy": "hybrid",
    "locations_text": ["New York, NY"],
    "posted_at": "2024-05-01T12:00:00Z",
    "expires_at": null,
    "language": "en",
    "content_hash": "abc123",
    "version": 3,
    "created_at": "2024-05-01T13:00:00Z",
    "updated_at": "2024-05-02T09:00:00Z",
    "is_active": true
  }
  ```
- **Retention & archive**
  - Active jobs kept for 180 days after `expires_at`/inactive; history retained 1 year; raw fetches 90 days in cold storage; deletions via lifecycle policies in S3; periodic vacuum/analyze and partitioning by month for `jobs`/`raw_fetches`.
  - Backups: daily RDS snapshots with PITR; restore rehearsal quarterly; checksum verification for S3 objects.

## 4) Implementation Blueprint
- **Recommended stack**
  - Frontend: Next.js (React/TypeScript, Tailwind, shadcn/ui), SSR/ISR; hosted on Vercel/Netlify.
  - Backend API: FastAPI + Postgres (RDS) + Redis; Celery workers; Playwright fetchers in container pool; object storage S3; OpenSearch for search (or Meilisearch for speed to MVP).
  - Auth/Payments: Stripe Billing; JWT sessions; email via Postmark/SendGrid; file storage on S3.
  - IaC modules: VPC + subnets, RDS, Redis, S3, OpenSearch, ECS services (API/workers/playwright), CloudFront, ACM certs, Secrets Manager parameters, PagerDuty integration.
- **Key endpoints/pages & flows**
  - Public: landing, pricing, SEO job listings by category/location, job detail (paywall after teaser), sitemap/robots.
  - Auth flows: signup/login, email verification, password reset, billing portal, subscription status banner.
  - App: search with filters (location, remote, salary, tags), saved jobs, applied status, user profile.
  - Alerts (optional MVP+): saved search → email digest.
  - API sketch: `/api/jobs` (search with pagination/filter params), `/api/jobs/{id}`, `/api/saved-jobs`, `/api/alerts`, `/api/admin/sources`, `/api/admin/resync/{source_id}`, `/api/admin/metrics/{source_id}`.
  - Request/response contract versioned (e.g., `v1` namespace); consistent envelope `{data, meta, errors}`.
- **Admin tools**
  - Source registry CRUD; toggle enable/disable; adjust schedule/rate limit; trigger immediate re-scrape; view per-source metrics and logs; inspect captured HTML snapshots; error triage queue with resolution notes.
  - Workflow: per-source health scorecard; diff view of parser configs; “promote from staging” button; download fixture pack for local parser testing.
- **Deployment plan**
  - CI: lint/test, type-check, Docker build, migrations. CD: staging → prod with manual approval. IaC via Terraform for VPC, RDS, Redis, S3, OpenSearch, ECS/Fargate workers, CloudFront CDN. Migrations via Alembic managed in repo. Playwright workers scaled separately with autoscaling on queue depth.
  - Feature flags for risky connector changes; blue/green for API; worker canary pool subscribed to subset of sources before fleet rollout.

## 5) Acceptance Criteria
- **SLOs**: 99.5% uptime; 95% scrape success per source daily; 90% of jobs refreshed within 24h of change; search page LCP <2.5s P75; dedupe precision ≥0.98, recall ≥0.95 on benchmark set.
- **MVP Done**
  - 50+ sources onboarded; scheduler + queue live; dedupe and versioning active; paywall enforced; SEO pages render structured data; basic admin source toggles; alerts/metrics for failures.
- **V1 Done**
  - 200+ sources with automated health scoring; adaptive rate limiting; alert digests; full admin error triage; auto sitemap refresh; A/B-tested landing; DR plan tested; cost dashboard with budgets/alerts.
  - Periodic red-team scraping compliance review; rolling parser fixture coverage >90% for active sources; end-to-end freshness test suite.

## 6) Maintenance Handoff
- **Runbook (examples)**
  - High 429/403: lower rate limit for source, enable backoff, verify robots/ToS, rotate IP or use official feed.
  - Parser break: disable source, capture sample HTML from S3, patch connector, run regression fixtures, redeploy.
  - Queue backlog: scale workers, prune stuck tasks, confirm scheduler cadence, check external latency.
  - Stripe webhook failures: replay via Stripe dashboard after fixing endpoint.
- **Add a new source steps**
  1) Create connector class template (fetch → parse → yield normalized job dict) with fixtures.
  2) Add source config (schedule, rate limit, auth headers, compliance notes) in registry.
  3) Write parser unit tests using stored HTML; add contract test through worker.
  4) Run dry-run job → validate normalized records → enable in staging → promote to prod.
- **Cost controls & scaling**
  - Autoscale workers on queue depth; cap Playwright usage via budget alarms; prefer RSS/API to reduce render cost.
  - Storage lifecycle rules; right-size OpenSearch; cache popular searches; consider tiered plans limiting API/search volume.
  - Periodic ROI review per source (cost per valid job) to disable low-value sources.

## 7) Execution Roadmap (What to do next)
- **Week 0–1: Foundation**
  - Stand up repos with CI (lint/test/type-check), IaC scaffolding (Terraform skeleton for VPC/RDS/Redis/S3/OpenSearch), and base FastAPI + Next.js apps.
  - Wire Stripe sandbox + auth flows; add feature-flag service; seed admin user.
  - Implement baseline schema with migrations; create connector SDK skeleton (interface, config loader, rate limiter, DLQ hooks).
- **Week 2–3: Ingestion + Dedupe core**
  - Build first three connector templates (RSS/API, static HTML, Playwright) with fixtures and contract tests.
  - Implement scheduler + queue wiring, idempotent upsert pipeline, and dedupe/versioning tables.
  - Add observability (OTel traces, Prometheus metrics) and admin source registry CRUD.
- **Week 4–6: Search UX + Paywall**
  - Ship search/browse with filters, SSR job detail pages with JSON-LD, sitemap generation, and paywall gating.
  - Add saved jobs, basic alerts, and subscription state awareness in UI.
  - Harden SEO performance budgets (LCP <2.5s P75) and caching (CDN + Redis).
- **Week 7–8: Hardening + Scale-Out**
  - Onboard 50+ sources using template; add health scoring and automated disable on poor quality.
  - Implement cost dashboards, budget alerts, and source ROI scoring.
  - DR runbook rehearsal; blue/green deploys for API and worker canary pool; load test ingestion/search paths.
- **Ongoing: Governance & Compliance**
  - Quarterly robots/ToS reviews per source; rotate secrets; renew TLS; review RLS policies and audit logs.
  - Accessibility audits for UI; monitoring for scraping blocks; fixture coverage >90% for active connectors.
- **Critical risks to watch**
  - Playwright cost/latency creep: set per-source render budgets and prefer API/RSS fallbacks.
  - Dedupe false positives: keep labeled benchmark set; monitor precision/recall alerts before auto-disable.
  - SEO thin-content penalties: ensure unique descriptions and canonicalization; avoid indexable empty filters.
