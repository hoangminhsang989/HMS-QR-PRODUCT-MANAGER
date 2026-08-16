"""Environment-separated authority for generated QR, label, and Excel outputs."""

from __future__ import annotations

import os
from pathlib import Path

from config.environments import ENVIRONMENT_ENV, Environment
from config.paths import (
    PathConfigurationError,
    require_external_runtime_root,
    require_test_path,
    require_test_root,
)


GENERATED_ASSET_ROOT_ENV = "HMS_QR_GENERATED_ASSET_ROOT"


def generated_asset_root(environment: Environment | str | None = None) -> Path:
    """Resolve generated-output authority without source, CWD, or profile fallback."""

    selected = environment if environment is not None else os.environ.get(
        ENVIRONMENT_ENV, Environment.DEV.value
    )
    try:
        current = Environment(str(selected).strip().lower())
    except ValueError:
        raise PathConfigurationError("HMS_QR_ENV must be dev, staging, or prod.") from None
    if current is Environment.DEV:
        return require_test_root()
    return require_external_runtime_root(GENERATED_ASSET_ROOT_ENV)


def require_generated_asset_path(
    path: str | Path,
    *,
    environment: Environment | str | None = None,
) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise PathConfigurationError("generated asset paths must be absolute")
    target = candidate.resolve(strict=False)
    root = generated_asset_root(environment)
    if target != root and root not in target.parents:
        raise PathConfigurationError(
            "generated assets must stay under the configured generated-asset root"
        )
    return target


def require_test_output_path(path: str | Path) -> Path:
    """Compatibility boundary for callers that intentionally emit test evidence."""

    return require_test_path(path)


__all__ = [
    "GENERATED_ASSET_ROOT_ENV",
    "generated_asset_root",
    "require_generated_asset_path",
    "require_test_output_path",
]
