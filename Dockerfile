FROM python:3.14-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HMS_QR_ENV=prod

# libgl1/libglib are required by opencv-python on slim images; curl backs the healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN useradd --system --uid 10001 hmsqr \
    && chown -R hmsqr:hmsqr /app
USER hmsqr

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:8000/health/readiness/database" || exit 1

# PROD fails fast without HMS_QR_DATABASE_URL. Set it to a standalone absolute
# SQLite path: sqlite:////data/hms_qr.sqlite
#
# Do NOT reach for PostgreSQL here. The engine cutover (ADR-015) replaced it
# with packages/sqlengine, which is SQLite-only - it has no PostgreSQL code
# path at all - and psycopg is deliberately absent from requirements.txt
# (test_r010r2_database_runtime.py forbids it by name). validate_database_url
# still has a postgresql+psycopg branch, but it names a driver nothing installs
# and nothing imports, so configuring it gets past validation and then fails
# inside the engine.
#
# Migrations run before the API so a fresh container never serves a stale schema.
# Alembic is gone from the runtime; the engine migrations are what
# require_database_schema_current verifies against.
CMD ["sh", "-c", "python -c \"from config.environments import load_config; from packages.persistence.database import create_database_runtime; from packages.persistence.stage2_repository import Stage2Repository; runtime=create_database_runtime(load_config()); Stage2Repository(runtime).create_schema(); runtime.dispose()\" && exec uvicorn apps.server.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
