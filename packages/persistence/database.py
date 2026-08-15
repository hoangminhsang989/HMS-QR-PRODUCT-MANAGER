"""Authoritative database configuration, engine, session, and readiness policy.

The server owns this boundary.  Application code receives a ``DatabaseRuntime``
instead of constructing feature-specific engines, which keeps production
PostgreSQL credentials and connection policy on the server side.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from config.environments import (
    AppConfig,
    DatabaseConfigurationError,
    Environment,
    validate_database_url,
)


class DatabaseUnavailableError(RuntimeError):
    """Secret-free production startup failure."""


def redacted_database_url(value: str) -> str:
    """Return a diagnostic URL without credentials or raw secret text."""

    try:
        return make_url(value).render_as_string(hide_password=True)
    except Exception:
        return "<invalid-database-url>"


def sqlite_path(value: str):
    """Extract a SQLite path only after proving the URL is SQLite."""

    url = make_url(value)
    if url.get_backend_name() != "sqlite":
        raise DatabaseConfigurationError("A PostgreSQL URL cannot be used as a filesystem path.")
    from pathlib import Path

    return Path(url.database or "")


@dataclass(frozen=True, slots=True)
class DatabaseRuntime:
    config: AppConfig
    engine: Engine
    session_factory: sessionmaker[Session]

    @property
    def redacted_url(self) -> str:
        return redacted_database_url(self.config.database_url)

    def readiness(self) -> dict[str, object]:
        """Run one bounded, secret-free database probe."""

        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return {"state": "READY", "database": self.config.environment.value}
        except Exception:
            return {"state": "UNAVAILABLE", "database": self.config.environment.value}

    def dispose(self) -> None:
        self.engine.dispose()


def create_database_runtime(config: AppConfig) -> DatabaseRuntime:
    url = validate_database_url(config.environment, config.database_url)
    if config.environment is Environment.DEV:
        engine = create_engine(
            url,
            future=True,
            connect_args={"check_same_thread": False},
        )
    else:
        engine = create_engine(
            url,
            future=True,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            pool_timeout=30,
            pool_recycle=1800,
            connect_args={"connect_timeout": 5},
        )
    factory = sessionmaker(engine, expire_on_commit=False, autoflush=True)
    return DatabaseRuntime(config, engine, factory)


def require_database_ready(runtime: DatabaseRuntime) -> None:
    if runtime.readiness()["state"] != "READY":
        runtime.dispose()
        raise DatabaseUnavailableError("Required production database is unavailable.")


def create_database_runtime_for_url(value: str) -> DatabaseRuntime:
    """Compatibility helper for isolated repository tests and DEV callers."""

    backend = make_url(value).get_backend_name()
    environment = Environment.DEV if backend == "sqlite" else Environment.PROD
    return create_database_runtime(AppConfig(environment, value, "test"))


def resolve_database(value, session_factory=None):
    """Resolve a runtime, Engine, or isolated-test URL to one engine/factory pair."""

    if isinstance(value, DatabaseRuntime):
        return value.engine, value.session_factory
    if isinstance(value, Engine):
        return value, session_factory or sessionmaker(value, expire_on_commit=False)
    runtime = create_database_runtime_for_url(str(value))
    return runtime.engine, runtime.session_factory


def transaction_lock(session: Session, namespace: str, identity: str = "global") -> None:
    """Serialize a bounded logical mutation on PostgreSQL; SQLite is already serial."""

    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": f"hms-qr:{namespace}:{identity}"},
        )


@contextmanager
def session_scope(runtime: DatabaseRuntime) -> Iterator[Session]:
    """Yield one request-owned session and always rollback/close on failure."""

    session = runtime.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = [
    "DatabaseConfigurationError",
    "DatabaseRuntime",
    "DatabaseUnavailableError",
    "create_database_runtime",
    "create_database_runtime_for_url",
    "redacted_database_url",
    "require_database_ready",
    "resolve_database",
    "session_scope",
    "sqlite_path",
    "transaction_lock",
    "validate_database_url",
]
