from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.routers import analytics, auth, health, links, redirect

app = FastAPI(
    title="Linkforge API",
    version="0.1.0",
    description=(
        "URL shortener with analytics. Short links, redirect on GET /{slug}, "
        "per-user analytics and rate limits."
    ),
    openapi_tags=[
        {"name": "auth", "description": "Registration, login and session identity."},
        {"name": "links", "description": "CRUD for the current user's short links."},
        {"name": "analytics", "description": "Click analytics for owned links."},
        {"name": "redirect", "description": "Public short-link resolution."},
        {"name": "health", "description": "Liveness and dependency checks."},
    ],
)


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(links.router)
app.include_router(analytics.router)
# Registered LAST on purpose: /{slug} is a catch-all GET and must not
# shadow /health, /auth/*, /links/* or the docs routes.
app.include_router(redirect.router)
