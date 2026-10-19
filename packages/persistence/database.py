"""Authoritative database configuration, engine, and readiness policy.

The server owns this boundary.  Application code receives a ``DatabaseRuntime``
instead of constructing feature-specific engines, which keeps production
configuration and connection policy on the server side.

Persistence runs on the in-process HMS SQL engine (``packages.sqlengine``).
There is no network database, no connection pool, and no second writer: the
engine serializes writes on one lock and serves reads from the current
in-memory state, so the advisory-lock and pool-tuning machinery the previous
SQLAlchemy/PostgreSQL runtime needed is gone.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from config.dburl import make_url
from config.environments import (
    AppConfig,
    DatabaseConfigurationError,
    Environment,
    validate_database_url,
)
from config.paths import SOURCE_ROOT
from packages.sqlengine import Database
from packages.sqlengine.migrations import applied_versions, load_migration_modules


class DatabaseUnavailableError(RuntimeError):
    """Secret-free production startup failure."""


ENGINE_MIGRATION_DIRECTORY = SOURCE_ROOT / "migrations" / "engine"
ENGINE_PATH_SUFFIX = "-engine"


def redacted_database_url(value: str) -> str:
    """Return a diagnostic URL without credentials or raw secret text."""

    try:
        return make_url(value).render_as_string(hide_password=True)
    except Exception:
        return "<invalid-database-url>"


def sqlite_path(value: str) -> Path:
    """Extract a SQLite path only after proving the URL is SQLite."""

    url = make_url(value)
    if url.get_backend_name() != "sqlite":
        raise DatabaseConfigurationError("A PostgreSQL URL cannot be used as a filesystem path.")
    return Path(url.database or "")


def engine_path(value: str) -> Path:
    """Map a configured database URL onto the engine's database directory."""

    url = make_url(value)
    if url.get_backend_name() != "sqlite":
        raise DatabaseConfigurationError(
            "The HMS SQL engine stores one database directory per configured SQLite path."
        )
    database = url.database or ""
    if not database or database == ":memory:":
        raise DatabaseConfigurationError("The engine requires a concrete database directory.")
    base = Path(database)
    if base.suffix:
        base = base.with_suffix("")
    return base.parent / f"{base.name}{ENGINE_PATH_SUFFIX}"


@dataclass(frozen=True, slots=True)
class DatabaseRuntime:
    config: AppConfig
    database: Database
    path: Path

    @property
    def engine(self) -> Database:
        """Compatibility accessor: the engine database is the runtime's engine."""

        return self.database

    @property
    def session_factory(self):
        """Compatibility accessor: yields one write transaction per call."""

        return self.database.transaction

    @property
    def redacted_url(self) -> str:
        return redacted_database_url(self.config.database_url)

    def readiness(self) -> dict[str, object]:
        """Run one bounded, secret-free database probe."""

        try:
            state = self.database.readiness()["state"]
        except Exception:
            state = "UNAVAILABLE"
        return {"state": state, "database": self.config.environment.value}

    def dispose(self) -> None:
        self.database.close()


def create_database_runtime(config: AppConfig) -> DatabaseRuntime:
    url = validate_database_url(config.environment, config.database_url)
    path = engine_path(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    database = Database(path)
    return DatabaseRuntime(config, database, path)


def require_database_ready(runtime: DatabaseRuntime) -> None:
    if runtime.readiness()["state"] != "READY":
        runtime.dispose()
        raise DatabaseUnavailableError("Required production database is unavailable.")


def _shipped_migration_versions() -> list[int]:
    if not ENGINE_MIGRATION_DIRECTORY.is_dir():
        return []
    return [version for version, _, _ in load_migration_modules(ENGINE_MIGRATION_DIRECTORY)]


def _applied_versions(runtime: DatabaseRuntime) -> set[int]:
    try:
        return applied_versions(runtime.database)
    except Exception:
        return set()


def require_database_schema_current(runtime: DatabaseRuntime) -> None:
    """Reject a production database until an operator applies the shipped migrations."""

    shipped = _shipped_migration_versions()
    if not shipped:
        runtime.dispose()
        raise DatabaseUnavailableError("No shipped engine migrations are available.")
    applied = _applied_versions(runtime)
    if not applied:
        runtime.dispose()
        raise DatabaseUnavailableError(
            "Required production database schema is unavailable or uninitialized."
        )
    if max(applied) < max(shipped):
        runtime.dispose()
        raise DatabaseUnavailableError(
            "Required production database schema is not at the deployed migration revision."
        )


def database_schema_readiness(runtime: DatabaseRuntime) -> dict[str, object]:
    """Return secret-free schema state without mutating the database."""

    if runtime.config.environment is Environment.DEV:
        return {"state": "NOT_REQUIRED"}
    shipped = _shipped_migration_versions()
    if not shipped:
        return {"state": "UNAVAILABLE"}
    applied = _applied_versions(runtime)
    if not applied:
        return {"state": "UNAVAILABLE"}
    return {"state": "READY" if max(applied) >= max(shipped) else "STALE"}


def create_database_runtime_for_url(value: str) -> DatabaseRuntime:
    """Compatibility helper for isolated repository tests and DEV callers."""

    backend = make_url(value).get_backend_name()
    environment = Environment.DEV if backend == "sqlite" else Environment.PROD
    return create_database_runtime(AppConfig(environment, value, "test"))


def resolve_database(value, session_factory=None) -> Database:
    """Resolve a runtime, engine database, or isolated-test URL to one engine."""

    if isinstance(value, DatabaseRuntime):
        return value.database
    if isinstance(value, Database):
        return value
    return create_database_runtime_for_url(str(value)).database


def transaction_lock(session, namespace: str, identity: str = "global") -> None:
    """No-op retained for call-site compatibility.

    The engine has exactly one writer per process and serializes every write
    transaction on a single lock, so the logical namespace locks the previous
    PostgreSQL runtime needed are already provided by the engine itself.
    """

    return None


@contextmanager
def session_scope(runtime: DatabaseRuntime) -> Iterator:
    """Yield one request-owned write transaction; roll back and release on failure."""

    with runtime.database.transaction() as transaction:
        yield transaction


__all__ = [
    "DatabaseConfigurationError",
    "DatabaseRuntime",
    "DatabaseUnavailableError",
    "ENGINE_MIGRATION_DIRECTORY",
    "create_database_runtime",
    "create_database_runtime_for_url",
    "database_schema_readiness",
    "engine_path",
    "redacted_database_url",
    "require_database_ready",
    "require_database_schema_current",
    "resolve_database",
    "session_scope",
    "sqlite_path",
    "transaction_lock",
    "validate_database_url",
]
