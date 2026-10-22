# ---- Stage 1: build deps into an isolated prefix ---------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
COPY requirements.txt .
# --prefix keeps everything in one copyable tree; system plumbing stays out
# of the final image.
RUN pip install --prefix=/install -r requirements.txt

# ---- Stage 2: slim runtime, non-root ----------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN addgroup --system forge \
    && adduser --system --ingroup forge forge

WORKDIR /app
COPY --from=builder /install /usr/local
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

USER forge

EXPOSE 8000
# Render sets PORT; default 8000 locally. Migrations run at boot: the
# database must be reachable by then (Render service ordering handles this;
# the DB add-on is provisioned before the web service starts).
CMD ["sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
