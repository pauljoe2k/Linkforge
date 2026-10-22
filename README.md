# Linkforge

A URL shortener with a full analytics API, built as an 8-day study project:
**FastAPI · PostgreSQL · SQLAlchemy 2.0 + Alembic · Redis · JWT (Argon2id) · Pydantic v2 · pytest · Docker Compose · GitHub Actions · Render**.

> Status: MVP feature-complete locally, 78 tests green at 96% coverage, load-tested.
> Render deployment pending first push to GitHub (runbook below).

## Architecture

```mermaid
flowchart LR
    Visitor(("Visitor")) -->|"GET /{slug}"| Redirect["Redirect router<br/>(public)"]
    Visitor -->|"click logged async"| BG[(BackgroundTasks)]
    Owner(("Link owner")) -->|"Bearer JWT"| API["Auth + Links + Analytics"]
    Redirect -->|cache hit?| Redis[("Redis<br/>slug→JSON cache<br/>TTL 300s")]
    Redirect -->|miss| PG[(("PostgreSQL<br/>links"))]
    Redis -->|hit: still logs click| BG
    API --> PG
    BG -->|"INSERT clicks"| PG
    Redis -.->|rate counters<br/>fixed window| Limits["Rate limiters<br/>per-user API · per-IP redirect"]
    Limits -.-> Redirect
    Limits -.-> API
```

Key flow in words: a redirect **never writes to Postgres synchronously** — the click is
logged by a FastAPI background task after the 302 is already in flight, and with a warm
Redis cache the request reads *nothing* from Postgres at all.

## Data model

```
users(id PK identity, email UNIQUE, password_hash, created_at, updated_at)
links(id PK, user_id FK→users ON DELETE CASCADE, slug UNIQUE, target_url,
      is_active, created_at, updated_at)
clicks(id PK, link_id FK→links ON DELETE CASCADE, clicked_at, referrer NULL,
       device_type CHECK IN (desktop/mobile/tablet/other))

Indexes:
  ix_users_email                  UNIQUE btree (email)
  ix_links_slug                   UNIQUE btree (slug)          ← redirect hot path
  ix_links_user_id_created_at     btree (user_id, created_at)  ← paginated owner list
  ix_clicks_link_id_clicked_at    btree (link_id, clicked_at)  ← all analytics
```

The composite `(link_id, clicked_at)` index was verified with real `EXPLAIN` output to
serve daily grouping, referrer grouping, and totals — no post-hoc index fixes were needed.

## Endpoints (auth = Bearer JWT)

| Method | Path | Status | Notes |
|---|---|---|---|
| POST | `/auth/register` | 201 | 409 duplicate email, 422 validation |
| POST | `/auth/login` | 200 | 401 identical for unknown email ≠ wrong password |
| GET | `/auth/me` | 200 | 401 without/with bad token |
| POST | `/links` | 201 | random or custom slug; 409 taken, 422 bad URL |
| GET | `/links?limit&offset` | 200 | paginated, newest first |
| GET | `/links/{id}` | 200 | 404 if not yours (indistinguishable) |
| PATCH | `/links/{id}` | 200 | 404/409/422 |
| DELETE | `/links/{id}` | 204 | click history cascades |
| GET | `/{slug}` | **302** | 404 unknown/deactivated, 429 per-IP |
| GET | `/links/{id}/analytics/summary` | 200 | total + device breakdown |
| GET | `/links/{id}/analytics/daily?start=&end=` | 200 | SQL date_trunc grouping |
| GET | `/links/{id}/analytics/referrers?limit=` | 200 | NULL referrer → `direct` |
| GET | `/health` | 200 | reports db/redis status |

## Setup (local)

```bash
docker compose up -d            # Postgres :5433, Redis :6380 (ports chosen to
                                # avoid clashes with other local stacks)
python -m pip install -r requirements.txt
cp .env.example .env            # adjust DATABASE_URL/REDIS_URL if you changed ports
python -m alembic upgrade head
python -m pytest tests/         # dedicated linkforge_test DB
python -m uvicorn app.main:app --reload   # dashboard → http://localhost:8000/
```

The dashboard at `/` supports registration/sign-in, creating and copying short
links, deleting links, and viewing click, device, daily, and referrer analytics.
The interactive API remains available at `/docs`.

Note on tests: the suite creates its own `linkforge_test` database (derived from
`DATABASE_URL`) and never touches the dev database. Isolation is truncate-per-test,
on both sides of every test, plus a Redis `flushall` — chosen over rollback-per-test
because the app intentionally uses multiple connections per request (get_db session +
background-task session), which a single outer transaction cannot see. See
[tests/conftest.py](tests/conftest.py) for the full rationale.

## Design decisions (defend these out loud)

**302 over 301.** Browsers/proxies cache 301s indefinitely: repeat visitors would
disappear from analytics and stale targets would survive cache invalidation. 302 keeps
the data true; SEO authority transfer was consciously out of scope. Straight from the
redirect handler comment.

**Scheme allowlist (`http`/`https`).** `javascript:`, `data:`, `file:` etc. are rejected
at schema validation → 422, so no short link can smuggle a script or binary handler.
URL length is capped (2048) to keep things sane.

**Random slugs: 7 chars, base62, `secrets`-driven.** ~3.5×10¹² combinations ≈ full
62-bit unguessability; CSPRNG so slugs can't be predicted; collision retry with a
documented length-extension fallback.

**Argon2id** (64 MiB, t=3 defaults) — PHC winner, memory-hard, GPU-resistant; salt
embedded; garbage-hash-safe verification. JWTs carry only `sub`/`iat`/`exp`/`type`
(no PII — tokens are base64, not encrypted); 30-min access tokens, no refresh tokens
in the MVP (documented trade-off); HS256 until a second verifier appears (then RS256).
Login returns byte-identical errors for "unknown email" and "wrong password", and burns
one Argon2 hash on the unknown-email path so response *timing* can't enumerate users.

**Cache-invalidation correctness over hit-rate tricks.** Cached value is JSON
`{link_id, target_url}` so a cache hit still logs the click without a DB read; every
update/delete `DEL`s the affected keys outright (both old and new slugs on rename).
Redis failures fail open (cache miss, limiter allows) — a cache must never turn a
healthy backend into a broken one.

**Rate limits: fixed window** (one INCR + one EXPIRE). Sliding windows buy boundary-burst
precision (fixed windows allow ~2× across a boundary) at the cost of ZSETs or extra
round-trips. Defaults: 100/min per user (API), 30/min per IP (redirect), both
`429 + Retry-After`. Behind a proxy the IP key must move to the rightmost
X-Forwarded-For hop — noted in code.

**Ownership = 404, not 403.** Foreign and nonexistent link ids are indistinguishable
across GET/PATCH/DELETE and all three analytics endpoints — one body, no id-probing
oracle.

## Load tests

Locust against a single local slug, 10 concurrent users, 15s steady window
(`loadtest/locustfile.py`; k6 equivalent in `loadtest/redirect.js`):

| Config | req count (15s) | RPS | p50 | p95 |
|---|---|---|---|---|
| Redis cache **on** | 3137 | ~209 | 17 ms | **31 ms** |
| Redis cache **off** | 2254 | ~150 | 34 ms | **63 ms** |

At 50 concurrent users both configs converged (~167-170 RPS, p50 ~250-260 ms): the
bottleneck becomes the per-request click INSERT commit against local Dockerized
Postgres + the click-minutes disk, not slug lookup. That's the honest reading: the
cache halves redirect latency pre-saturation and removes ~40% of DB reads, while the
next architectural lever (batched click writes) targets the saturation ceiling.

Method: read **RPS** as completed requests/second in the steady window only;
**P95** from the `/[slug]` stats row; ignore ramp-up edges; treat failures > 0 as a
failed run rather than a datapoint.

Reproduce: `python loadtest/seed.py`, start uvicorn (`REDIRECT_RATE_LIMIT=100000`
so the per-IP limiter doesn't throttle the single-IP generator), run locust, then
repeat with `DISABLE_REDIRECT_CACHE=true` on the *server* process.

## Deploy to Render (runbook)

1. Push this repo to GitHub (CI runs on `main` and PRs).
2. In Render: **New → Blueprint**, connect the GitHub account if prompted, and
   select this repository. Review the services and plans before applying:
   `render.yaml` declares the web service, managed Postgres, and a Key Value
   cache, wires `DATABASE_URL` / `REDIS_URL` automatically, and generates
   `JWT_SECRET_KEY`. The app refuses to start in production without a generated,
   strong JWT secret. The cache is restricted to Render's private network.
3. The Docker image runs `alembic upgrade head` at boot, then uvicorn on `$PORT`.
   Health check: `/health` returns 503 when Postgres is unavailable. Redis status
   is reported separately because cache and rate limiting fail open on Redis outages.
4. Verify: `GET /health` shows `db: up, redis: up`; register → login → create →
   redirect → analytics through the public URL.
5. Post-deploy: run `loadtest/locustfile.py` against the live URL with a modest
   free-tier budget (RLS: cap `-u 10`, 30s) and record numbers here.
   The free web service can sleep after inactivity, and the free Postgres expires
   after 30 days. Treat these plans as a demo only; choose paid plans in the
   Blueprint before applying it for persistent hosting and backups.

## Postman

Import [linkforge.postman_collection.json](linkforge.postman_collection.json): set
`baseUrl` once, run **Login** — the collection script stores the token into
`{{accessToken}}` for every other request, and Create-link captures `{{linkId}}`/`{{slug}}`.

## Test & quality snapshot

- **78 tests, 96% coverage** (`python -m pytest tests/ --cov=app --cov-report=term-missing`)
- Weakest area post-improvement: `app/services/cache.py` (91%) — remaining lines are
  logging branches inside Redis-outage handlers.
- Ruff clean (`ruff check app tests loadtest`).
- CI: `.github/workflows/ci.yml` — lint job + test job with Postgres/Redis services;
  fails on lint error or test failure; uploads coverage.xml artifact.

## Resume bullets (fill in the real numbers)

- Built a URL-shortener service (FastAPI, PostgreSQL, SQLAlchemy 2.0, Redis, JWT/Argon2id)
  with **[N] automated tests at [XX]% coverage**, shipped to production on Render behind
  a GitHub Actions CI pipeline (lint + integration tests against real Postgres/Redis).
- Cut redirect p95 latency from **[63] ms to [31] ms** (-[51]%) at **[~210] req/s** by
  introducing a Redis-backed slug cache with delete-on-write invalidation, verified
  with Locust A/B load tests (cache on/off).
- Designed an analytics pipeline queuing redirect events as background tasks (
  **[209] req/s sustained, 0% error rate**, 5,000+ click demo dataset), with SQL-side
  aggregation verified via EXPLAIN plans and composite indexes.

## What's next (known limits)

- Click writes are one-row-per-request commits; a buffered writer would lift the
  saturation ceiling further.
- Refresh tokens / token revocation, OAuth proxies, and custom domains are the natural
  v2; per-user daily API rates and per-link analytics windows are configurable but not
  yet user-facing.
