"""Portable source and externally configured runtime path authorities."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT_ENV = "HMS_QR_TEST_ROOT"


class PathConfigurationError(ValueError):
    """A required path authority is missing or unsafe."""


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


def _required_absolute_path(
    variable: str,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    source = os.environ if environ is None else environ
    raw = str(source.get(variable, "")).strip()
    if not raw or _is_placeholder(raw):
        raise PathConfigurationError(f"{variable} is missing or unresolved.")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        raise PathConfigurationError(f"{variable} must be an absolute path.")
    return candidate.resolve(strict=False)


def _is_at_or_beneath(candidate: Path, root: Path) -> bool:
    return candidate == root or root in candidate.parents


def require_test_root(*, environ: Mapping[str, str] | None = None) -> Path:
    """Return the explicit external test-harness root, never a source fallback."""

    root = _required_absolute_path(TEST_ROOT_ENV, environ=environ)
    if _is_at_or_beneath(root, SOURCE_ROOT):
        raise PathConfigurationError(
            f"{TEST_ROOT_ENV} must remain outside the source package."
        )
    return root


def require_test_path(
    path: str | Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Validate a generated test path against the injected test root."""

    candidate = Path(path)
    if not candidate.is_absolute():
        raise PathConfigurationError("test artifact paths must be absolute")
    target = candidate.resolve(strict=False)
    root = require_test_root(environ=environ)
    if not _is_at_or_beneath(target, root):
        raise PathConfigurationError("test artifacts must stay under the configured test root")
    return target


def require_external_runtime_root(
    variable: str,
    *,
    environ: Mapping[str, str] | None = None,
    reject_test_root: bool = True,
) -> Path:
    """Resolve an explicit persistent/runtime root outside source and test trees."""

    source = os.environ if environ is None else environ
    root = _required_absolute_path(variable, environ=source)
    return validate_external_runtime_path(
        root,
        authority=variable,
        environ=source,
        reject_test_root=reject_test_root,
    )


def validate_external_runtime_path(
    value: str | Path,
    *,
    authority: str,
    environ: Mapping[str, str] | None = None,
    reject_test_root: bool = True,
) -> Path:
    """Validate an explicit persistent path without CWD or personal-profile authority."""

    candidate = Path(value)
    if not candidate.is_absolute():
        raise PathConfigurationError(f"{authority} must be an absolute path.")
    root = candidate.resolve(strict=False)
    if _is_at_or_beneath(root, SOURCE_ROOT):
        raise PathConfigurationError(f"{authority} must remain outside the source package.")
    source = os.environ if environ is None else environ
    configured_test_root = str(source.get(TEST_ROOT_ENV, "")).strip()
    if reject_test_root and configured_test_root:
        test_root = require_test_root(environ=source)
        if _is_at_or_beneath(root, test_root):
            raise PathConfigurationError(f"{authority} must remain outside the test root.")
    profile_raw = str(source.get("USERPROFILE", "")).strip()
    if profile_raw:
        profile = Path(profile_raw)
        if profile.is_absolute() and _is_at_or_beneath(root, profile.resolve(strict=False)):
            raise PathConfigurationError(
                f"{authority} must remain outside a personal user profile."
            )
    return root


def validate_paths() -> bool:
    """Validate the checked-out package and explicit test-harness authority."""

    return SOURCE_ROOT.is_dir() and require_test_root().is_dir()


__all__ = [
    "PathConfigurationError",
    "SOURCE_ROOT",
    "TEST_ROOT_ENV",
    "require_external_runtime_root",
    "require_test_path",
    "require_test_root",
    "validate_external_runtime_path",
    "validate_paths",
]
