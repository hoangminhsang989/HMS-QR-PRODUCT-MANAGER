"""Environment profiles. Secrets are injected externally and never committed."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from config.paths import TEST_ROOT


class Environment(StrEnum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


@dataclass(frozen=True, slots=True)
class AppConfig:
    environment: Environment
    database_url: str
    storage_backend: str
    storage_root: str | None = None


def load_config(environment: Environment | str = Environment.DEV) -> AppConfig:
    env = Environment(environment)
    if env is Environment.DEV:
        db = Path(TEST_ROOT, "db", "stage1_r002_dev.sqlite")
        return AppConfig(env, f"sqlite:///{db.as_posix()}", "local", str(TEST_ROOT / "storage"))
    if env is Environment.STAGING:
        return AppConfig(env, "${HMS_QR_STAGING_DATABASE_URL}", "configured")
    return AppConfig(env, "${HMS_QR_PROD_DATABASE_URL}", "nas")


__all__ = ["AppConfig", "Environment", "load_config"]
