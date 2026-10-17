"""Environment profiles. Secrets are injected externally and never committed."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import os
from pathlib import Path

from sqlalchemy.engine import make_url

from config.paths import require_external_runtime_root, require_test_root, validate_external_runtime_path


class Environment(StrEnum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


DATABASE_URL_ENV = "HMS_QR_DATABASE_URL"
ENVIRONMENT_ENV = "HMS_QR_ENV"


class DatabaseConfigurationError(ValueError):
    """Secret-safe environment/database configuration failure."""


def _is_placeholder(value: str) -> bool:
    lowered = value.casefold()
    return (
        "${" in value
        or "<" in value
        or ">" in value
        or "placeholder" in lowered
        or "changeme" in lowered
        or "replace-me" in lowered
        or "example" in lowered
    )


def validate_database_url(environment: Environment, value: str) -> str:
    """DEV requires SQLite; STAGING/PROD accept complete PostgreSQL or standalone absolute SQLite."""

    raw = str(value or "").strip()
    if environment is Environment.DEV:
        if not raw or not raw.startswith("sqlite:"):
            raise DatabaseConfigurationError("DEV requires a SQLite database URL.")
        return raw
    if not raw or _is_placeholder(raw):
        raise DatabaseConfigurationError(
            f"{environment.value.upper()} database configuration is missing or unresolved."
        )
    try:
        parsed = make_url(raw)
    except Exception:
        raise DatabaseConfigurationError(
            f"{environment.value.upper()} database URL is malformed."
        ) from None
    if parsed.get_backend_name() == "sqlite":
        database = parsed.database or ""
        if not database or database == ":memory:" or not Path(database).is_absolute():
            raise DatabaseConfigurationError(
                f"{environment.value.upper()} standalone SQLite requires an absolute file path."
            )
        return raw
    if parsed.get_backend_name() != "postgresql" or parsed.drivername != "postgresql+psycopg":
        raise DatabaseConfigurationError(
            f"{environment.value.upper()} requires the tracked PostgreSQL psycopg driver."
        )
    if not parsed.host or not parsed.database or not parsed.username or parsed.password in (None, ""):
        raise DatabaseConfigurationError(
            f"{environment.value.upper()} PostgreSQL URL is incomplete."
        )
    return raw


@dataclass(frozen=True, slots=True)
class AppConfig:
    environment: Environment
    database_url: str
    storage_backend: str
    storage_root: str | None = None

    def __repr__(self) -> str:
        return (
            "AppConfig(environment="
            f"{self.environment!r}, database_url='<redacted>', "
            f"storage_backend={self.storage_backend!r}, storage_root={self.storage_root!r})"
        )


def load_config(environment: Environment | str | None = None) -> AppConfig:
    selected = environment if environment is not None else os.environ.get(ENVIRONMENT_ENV, Environment.DEV.value)
    try:
        env = Environment(str(selected).strip().lower())
    except ValueError:
        raise DatabaseConfigurationError("HMS_QR_ENV must be dev, staging, or prod.") from None
    if env is Environment.DEV:
        configured_url = str(os.environ.get(DATABASE_URL_ENV, "")).strip()
        configured_storage = str(os.environ.get("HMS_QR_STORAGE_ROOT", "")).strip()
        if configured_url or configured_storage:
            if not configured_url or not configured_storage:
                raise DatabaseConfigurationError(
                    "DEV shared runtime requires both HMS_QR_DATABASE_URL and HMS_QR_STORAGE_ROOT."
                )
            database_url = validate_database_url(env, configured_url)
            database_path = Path(make_url(database_url).database or "")
            validate_external_runtime_path(database_path, authority=DATABASE_URL_ENV)
            storage_root = validate_external_runtime_path(
                configured_storage, authority="HMS_QR_STORAGE_ROOT"
            )
            return AppConfig(env, database_url, "local", str(storage_root))
        test_root = require_test_root()
        db = Path(test_root, "db", "stage1_r002_dev.sqlite")
        return AppConfig(env, f"sqlite:///{db.as_posix()}", "local", str(test_root / "storage"))
    database_url = validate_database_url(env, os.environ.get(DATABASE_URL_ENV, ""))
    if env is Environment.STAGING:
        return AppConfig(env, database_url, "configured")
    storage_root = require_external_runtime_root("HMS_QR_STORAGE_ROOT")
    return AppConfig(env, database_url, "local", str(storage_root))


__all__ = [
    "AppConfig",
    "DATABASE_URL_ENV",
    "DatabaseConfigurationError",
    "ENVIRONMENT_ENV",
    "Environment",
    "load_config",
    "validate_database_url",
]
