"""R011-WP1A-R1A2 runtime path portability and artifact leak gates."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig

import config.paths as paths_module
from config.environments import Environment, load_config
from config.paths import (
    PathConfigurationError,
    SOURCE_ROOT,
    TEST_ROOT_ENV,
    require_test_path,
    require_test_root,
)
from packages.deployment.artifact import (
    build_release,
    scan_release_payload_for_paths,
    verify_release,
)
from packages.deployment.configuration import (
    ConfigValidationError,
    production_config_template,
    validate_production_config,
)
from packages.generated_assets import (
    GENERATED_ASSET_ROOT_ENV,
    generated_asset_root,
    require_generated_asset_path,
)
from packages.excel.template_adapter import TemplatePreservingExporter


ROOT = Path(__file__).resolve().parents[2]


def _run(root: Path, *command: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _commit_fixture(root: Path, files: dict[str, str]) -> None:
    root.mkdir(parents=True)
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="")
    _run(root, "git", "init", "-q")
    _run(root, "git", "add", ".")
    _run(
        root,
        "git",
        "-c",
        "user.name=path-test",
        "-c",
        "user.email=path-test@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )


def _known_roots() -> tuple[str, str]:
    separator = chr(92)
    repository = "F:" + separator + separator.join(("PHAN-MEM-QUAN-LY-QR",))
    test_root = repository + "-FILE-CHAY-TEST"
    return repository, test_root


def test_source_root_is_structural_and_known_host_literals_are_absent():
    assert SOURCE_ROOT == Path(paths_module.__file__).resolve().parents[1]
    tracked = _run(ROOT, "git", "ls-files").stdout.splitlines()
    runtime_files = [
        ROOT / relative
        for relative in tracked
        if relative in {"alembic.ini", "pyproject.toml"}
        or relative.startswith(("apps/", "config/", "migrations/", "packages/", "scripts/"))
    ]
    repository, test_root = _known_roots()
    variants = {
        repository,
        repository.replace(chr(92), "/"),
        test_root,
        test_root.replace(chr(92), "/"),
    }
    findings = {
        path.relative_to(ROOT).as_posix(): value
        for path in runtime_files
        for value in variants
        if value.casefold() in path.read_text(encoding="utf-8", errors="ignore").casefold()
    }
    assert findings == {}


def test_alembic_default_has_no_database_path_authority():
    config = AlembicConfig(str(ROOT / "alembic.ini"))
    assert config.get_main_option("sqlalchemy.url") == ""
    with pytest.raises(Exception):
        alembic_command.upgrade(config, "head")


@pytest.mark.parametrize("value", ["", "relative/test-root", "<placeholder>"])
def test_test_root_requires_explicit_absolute_nonplaceholder_authority(value: str):
    with pytest.raises(PathConfigurationError):
        require_test_root(environ={TEST_ROOT_ENV: value})


def test_test_root_rejects_source_and_bounds_test_outputs(monkeypatch, tmp_path: Path):
    with pytest.raises(PathConfigurationError, match="outside the source"):
        require_test_root(environ={TEST_ROOT_ENV: str(SOURCE_ROOT / "test-output")})
    root = require_test_root()
    assert require_test_path(tmp_path / "proof.json") == (tmp_path / "proof.json").resolve()
    with pytest.raises(PathConfigurationError, match="configured test root"):
        require_test_path(SOURCE_ROOT / "forbidden.json")
    with pytest.raises(PathConfigurationError, match="absolute"):
        require_test_path("relative-output.json")
    monkeypatch.delenv(TEST_ROOT_ENV)
    with pytest.raises(PathConfigurationError, match="missing"):
        require_test_root()


def test_dev_paths_use_only_injected_test_root(monkeypatch, tmp_path: Path):
    monkeypatch.setenv(TEST_ROOT_ENV, str(tmp_path))
    monkeypatch.setenv("HMS_QR_ENV", "dev")
    config = load_config(Environment.DEV)
    assert Path(config.storage_root).resolve() == (tmp_path / "storage").resolve()
    assert (tmp_path / "db" / "stage1_r002_dev.sqlite").as_posix() in config.database_url
    assert generated_asset_root() == tmp_path.resolve()
    target = tmp_path / "generated" / "label.html"
    assert require_generated_asset_path(target) == target.resolve()
    with pytest.raises(PathConfigurationError):
        require_generated_asset_path(SOURCE_ROOT / "label.html")
    with pytest.raises(PathConfigurationError, match="absolute"):
        require_generated_asset_path("relative-label.html")


@pytest.mark.parametrize("environment", [Environment.STAGING, Environment.PROD])
def test_staging_and_prod_generated_paths_fail_closed_and_reject_test_root(
    monkeypatch, environment: Environment
):
    test_root = require_test_root()
    monkeypatch.setenv("HMS_QR_ENV", environment.value)
    monkeypatch.delenv(GENERATED_ASSET_ROOT_ENV, raising=False)
    with pytest.raises(PathConfigurationError, match="missing"):
        generated_asset_root()
    with pytest.raises(PathConfigurationError, match="missing"):
        TemplatePreservingExporter(allowed_output_root=SOURCE_ROOT / "exports")
    monkeypatch.setenv(GENERATED_ASSET_ROOT_ENV, str(test_root / "generated"))
    with pytest.raises(PathConfigurationError, match="outside the test root"):
        generated_asset_root()
    monkeypatch.setenv(GENERATED_ASSET_ROOT_ENV, str(SOURCE_ROOT / "generated"))
    with pytest.raises(PathConfigurationError, match="outside the source"):
        generated_asset_root()
    portable_runtime = Path("Z:/hms-qr-runtime/generated")
    monkeypatch.setenv(GENERATED_ASSET_ROOT_ENV, str(portable_runtime))
    assert generated_asset_root() == portable_runtime.resolve(strict=False)


def test_production_persistent_roots_are_explicit_and_reject_source_test_profile(
    monkeypatch,
):
    config = production_config_template()
    config.update(
        {
            "bind_address": "inventory-selected-interface",
            "port": 8080,
            "release_id": "release",
            "app_data_root": "Z:/synthetic-machine/app-data",
            "app_log_root": "Z:/synthetic-machine/app-logs",
            "local_ingest_root": "Z:/synthetic-machine/local-ingest",
        }
    )
    config["archive"]["identity"] = "archive-policy-v1"
    assert validate_production_config(config) is config
    for field, unsafe in (
        ("app_data_root", "relative/app-data"),
        ("app_log_root", str(SOURCE_ROOT / "logs")),
        ("local_ingest_root", str(require_test_root() / "ingest")),
    ):
        rejected = dict(config)
        rejected[field] = unsafe
        with pytest.raises(ConfigValidationError):
            validate_production_config(rejected)
    monkeypatch.setenv("USERPROFILE", "C:/Users/SyntheticOperator")
    profile_config = dict(config)
    profile_config["app_data_root"] = "C:/Users/SyntheticOperator/AppData/HMS"
    with pytest.raises(ConfigValidationError, match="personal user profile"):
        validate_production_config(profile_config)


def test_prod_config_and_imports_do_not_resolve_or_inherit_test_root(monkeypatch):
    test_root = require_test_root()
    monkeypatch.setenv("HMS_QR_ENV", "prod")
    monkeypatch.setenv(
        "HMS_QR_DATABASE_URL",
        "postgresql+psycopg://runtime-user:fixture-password@db.invalid/hms_qr",
    )
    monkeypatch.delenv(GENERATED_ASSET_ROOT_ENV, raising=False)
    config = load_config(Environment.PROD)
    assert config.storage_root is None
    assert str(test_root).casefold() not in repr(config).casefold()
    code = (
        "import config.paths, config.environments, packages.generated_assets; "
        "import packages.qr.service, packages.labels.service, packages.excel.template_adapter"
    )
    environment = os.environ.copy()
    environment.update(
        {
            "HMS_QR_ENV": "prod",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(ROOT),
        }
    )
    environment.pop(GENERATED_ASSET_ROOT_ENV, None)
    result = _run(ROOT, sys.executable, "-c", code, env=environment)
    assert result.stdout == "" and result.stderr == ""


def test_two_moved_module_roots_derive_their_own_source_location(tmp_path: Path):
    observed = []
    for relative in (Path("portable-a") / "repo", Path("different-parent") / "portable-b"):
        checkout = tmp_path / relative
        shutil.copytree(ROOT / "config", checkout / "config")
        environment = os.environ.copy()
        environment.update(
            {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(checkout),
                TEST_ROOT_ENV: str(require_test_root()),
            }
        )
        result = _run(
            checkout,
            sys.executable,
            "-c",
            "from config.paths import SOURCE_ROOT; print(SOURCE_ROOT)",
            env=environment,
        )
        observed.append(Path(result.stdout.strip()).resolve())
    assert observed == [
        (tmp_path / "portable-a" / "repo").resolve(),
        (tmp_path / "different-parent" / "portable-b").resolve(),
    ]
    assert observed[0] != observed[1]


def test_default_artifact_keeps_required_modules_and_scanner_detects_path_variants(
    tmp_path: Path,
):
    fixture = tmp_path / "scanner-source"
    canary = "Q:" + chr(92) + chr(92).join(("developer", "checkout"))
    _commit_fixture(
        fixture,
        {
            "config/paths.py": "SOURCE_ROOT = 'portable'\n",
            "packages/generated_assets.py": f"ROOT = r'{canary}'\n",
            "packages/__init__.py": "",
            "scripts/r011_collect_inventory_readonly.ps1": "param()\n'fixture'\n",
            "pyproject.toml": "[project]\nname='fixture'\nversion='0.0.0'\n",
        },
    )
    artifact = build_release(
        fixture,
        tmp_path / "artifact-output",
        release_id="scanner",
        build_timestamp="2026-08-16T00:00:00+00:00",
    )
    manifest = verify_release(artifact)
    included = {entry["path"] for entry in manifest["files"]}
    assert {
        "config/paths.py",
        "packages/generated_assets.py",
        "scripts/r011_collect_inventory_readonly.ps1",
    } <= included
    findings = scan_release_payload_for_paths(
        artifact,
        [canary.replace(chr(92), "/")],
    )
    assert findings == (
        {"path": "packages/generated_assets.py", "forbidden_root": canary.replace(chr(92), "/")},
    )
