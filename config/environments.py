"""Environment profiles. Secrets are injected externally and never committed."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import os
from pathlib import Path

from sqlalchemy.engine import make_url

from config.paths import TEST_ROOT


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
    """Enforce SQLite for DEV and psycopg/PostgreSQL for STAGING/PROD."""

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
        db = Path(TEST_ROOT, "db", "stage1_r002_dev.sqlite")
        return AppConfig(env, f"sqlite:///{db.as_posix()}", "local", str(TEST_ROOT / "storage"))
    database_url = validate_database_url(env, os.environ.get(DATABASE_URL_ENV, ""))
    if env is Environment.STAGING:
        return AppConfig(env, database_url, "configured")
    return AppConfig(env, database_url, "nas")


__all__ = [
    "AppConfig",
    "DATABASE_URL_ENV",
    "DatabaseConfigurationError",
    "ENVIRONMENT_ENV",
    "Environment",
    "load_config",
    "validate_database_url",
]
