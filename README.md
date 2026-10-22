# Linkforge

Linkforge turns long URLs into short links and tracks how people use them.
It includes a web dashboard, a REST API, and click analytics.

## Features

- Create accounts and sign in.
- Create random or custom short links.
- Update, deactivate, and delete your links.
- Track total clicks, device types, daily activity, and referrers.
- Cache redirects with Redis and rate-limit API requests.
- Explore the API at `/docs`.

## Built with

FastAPI · PostgreSQL · SQLAlchemy · Alembic · Redis · JWT · Argon2id · Docker

## Run locally

### Requirements

- Python 3.12
- Docker Desktop with Docker Compose

### Start the app

From the repository root, run:

```powershell
docker compose up -d
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Open the dashboard at [http://localhost:8000](http://localhost:8000).
The API documentation is at [http://localhost:8000/docs](http://localhost:8000/docs).

The local Docker services use PostgreSQL on port `5433` and Redis on port
`6380`. The `.env.example` file is configured for these ports. Keep `.env`
local; do not use its localhost URLs or development secret in a hosted service.

### Run tests and lint

Tests use a separate `linkforge_test` database derived from `DATABASE_URL`.
Make sure the local Postgres and Redis services are running first.

```powershell
python -m pytest tests/ --cov=app --cov-report=term-missing
python -m ruff check app tests loadtest
```

## API overview

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/auth/register` | Create an account |
| `POST` | `/auth/login` | Sign in and receive an access token |
| `GET` | `/auth/me` | Get the signed-in user |
| `POST` | `/links` | Create a short link |
| `GET` | `/links` | List your links |
| `GET`, `PATCH`, `DELETE` | `/links/{id}` | Read, update, or delete one of your links |
| `GET` | `/{slug}` | Redirect to the destination and record a click |
| `GET` | `/links/{id}/analytics/summary` | View total clicks and device breakdown |
| `GET` | `/links/{id}/analytics/daily` | View clicks per day |
| `GET` | `/links/{id}/analytics/referrers` | View top traffic sources |
| `GET` | `/health` | Check service and dependency status |

Management and analytics endpoints require a bearer token. Link ownership is
checked on every request. Short-link destinations must use `http` or `https`.

## How redirects and analytics work

Redirect lookups use Redis when available and fall back to PostgreSQL on a
cache miss or Redis outage. Link changes invalidate affected cache entries.
The app returns a temporary `302` redirect so future visits can be counted and
updated destinations can take effect.

Click events are saved in a background task after the redirect is prepared.
Analytics are aggregated in PostgreSQL and include total clicks, device type,
daily counts, and referrers. Visits without a referrer are grouped as `direct`.

## Deploy to Render

The repository includes a Render Blueprint in [`render.yaml`](render.yaml).
In Render, choose **New → Blueprint**, connect this repository, and review the
services before applying the Blueprint. It defines:

- A Docker web service.
- A PostgreSQL database.
- A Redis-compatible Key Value service.

The Blueprint wires the hosted database and cache URLs into the app and
generates a production JWT secret. The Docker container applies Alembic
migrations before starting the web server. After deployment, check
`https://<your-service>.onrender.com/health`, then open the service URL to use
the dashboard.

Review Render's current plan and pricing before applying. The Blueprint uses
free plans; the web service may sleep when idle, and the free PostgreSQL
database expires after 30 days. Choose a persistent plan for data you need to
keep. Never set hosted environment variables to local `localhost` URLs or the
development JWT secret.

## CI

GitHub Actions runs on pushes to `main` and pull requests. It builds the Docker
image, runs Ruff, and runs the tests with PostgreSQL and Redis services.

## Project layout

```text
app/
  routers/       API endpoints
  schemas/       Request and response validation
  services/      Authentication, links, cache, rate limits, analytics
  models/        Database models
  static/        Browser dashboard
alembic/         Database migrations
tests/            Automated tests
loadtest/         Locust and k6 redirect load tests
Dockerfile        Production container
render.yaml       Render Blueprint
```

## Load testing

The repository includes a Locust test and a k6 script for the public redirect
endpoint. To seed a local link and run Locust:

```powershell
python loadtest/seed.py
python -m locust -f loadtest/locustfile.py --headless -u 10 -r 10 --run-time 30s --host http://localhost:8000
```

Set `LINKFORGE_SLUG` if you want to test a slug other than `loadtest`. To
compare cache behavior, set `DISABLE_REDIRECT_CACHE=true` on the application
process and repeat the run. Treat results as failed if the test reports
request failures.
