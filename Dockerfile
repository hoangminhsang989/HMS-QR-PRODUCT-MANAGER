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

# PROD fails fast without HMS_QR_DATABASE_URL (postgresql+psycopg://user:password@host:5432/db).
# Migrations run before the API so a fresh container never serves a stale schema.
# Alembic is gone from the runtime; the engine migrations are what
# require_database_schema_current verifies against.
CMD ["sh", "-c", "py -3.14 -c \"from config.environments import load_config; from packages.persistence.database import create_database_runtime; from packages.persistence.sqlalchemy_repository import Stage2Repository; runtime=create_database_runtime(load_config()); Stage2Repository(runtime).create_schema(); runtime.dispose()\" && exec uvicorn apps.server.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
