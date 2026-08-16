"""Fail-closed pytest routing to the explicitly configured external test root."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from config.paths import PathConfigurationError, require_test_path, require_test_root


PYTEST_CACHE_DIR_ENV = "HMS_QR_PYTEST_CACHE_DIR"


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    try:
        root = require_test_root()
        requested_basetemp = config.option.basetemp or root / "pytest-temp"
        basetemp = require_test_path(requested_basetemp)
        requested_cache = (
            os.environ.get(PYTEST_CACHE_DIR_ENV, "").strip() or root / "pytest-cache"
        )
        cache_dir = require_test_path(requested_cache)
        Path(basetemp).parent.mkdir(parents=True, exist_ok=True)
        Path(cache_dir).parent.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(basetemp)
        config._inicache["cache_dir"] = str(cache_dir)
    except PathConfigurationError as exc:
        raise pytest.UsageError(str(exc)) from None
