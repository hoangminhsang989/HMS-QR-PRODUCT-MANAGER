"""R010R2 production database configuration and runtime acceptance."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import os
from pathlib import Path
import subprocess
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from apps.server.app import build_api
from apps.server.files import require_production_storage_ready
from config.dburl import make_url
from config.environments import (
    AppConfig,
    DATABASE_URL_ENV,
    DatabaseConfigurationError,
    ENVIRONMENT_ENV,
    Environment,
    load_config,
    validate_database_url,
)
from packages.persistence.database import (
    DatabaseRuntime,
    DatabaseUnavailableError,
    create_database_runtime,
    redacted_database_url,
    require_database_schema_current,
    session_scope,
    sqlite_path,
)
from packages.persistence.managed_file_repository import ManagedFileRepository
from packages.persistence.sqlalchemy_product_repository import SqlAlchemyProductRepository
from packages.persistence.sqlalchemy_repository import Stage2Repository
from packages.persistence.store_forward_repository import StoreForwardRepository
from packages.persistence.tracking_repository import TrackingRepository
from packages.persistence.workflow_repository import WorkflowRepository
from packages.application.server_auth import ServerAuthService, UserRole


LEGACY_POSTGRESQL_URL = "postgresql+psycopg://user:password@localhost/hms_qr"


def _prod_runtime(database):
    """A real PROD runtime over an existing engine database."""

    return DatabaseRuntime(
        AppConfig(Environment.PROD, LEGACY_POSTGRESQL_URL, "nas"),
        database,
        getattr(database, "path", None),
    )


def _stamp(database, versions: list[tuple[int, str]]) -> None:
    with database.transaction() as transaction:
        if not database.schema.has_table("_hms_migrations"):
            transaction.execute(
                "CREATE TABLE _hms_migrations ("
                "version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
            )
        transaction.execute("DELETE FROM _hms_migrations")
        for version, name in versions:
            transaction.execute(
                "INSERT INTO _hms_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                [version, name, "2026-01-01T00:00:00+00:00"],
            )


def test_staging_and_prod_database_configuration_fail_closed(monkeypatch):
    for environment in (Environment.STAGING, Environment.PROD):
        monkeypatch.delenv(DATABASE_URL_ENV, raising=False)
        with pytest.raises(DatabaseConfigurationError):
            load_config(environment)
        for invalid in (
            "",
            "${HMS_QR_DATABASE_URL}",
            "sqlite:///relative.sqlite",
            "mysql://host/database",
            "postgresql://user@host/database",
            "postgresql+psycopg://user@host/database",
            "postgresql+psycopg://",
        ):
            with pytest.raises(DatabaseConfigurationError):
                validate_database_url(environment, invalid)


def test_staging_and_prod_accept_standalone_absolute_sqlite(tmp_path):
    absolute = f"sqlite:///{(tmp_path / 'standalone.sqlite').as_posix()}"
    for environment in (Environment.STAGING, Environment.PROD):
        assert validate_database_url(environment, absolute) == absolute
    for invalid in (
        "sqlite:///relative.sqlite",
        "sqlite:///:memory:",
        "sqlite://",
        "mysql://host/database",
    ):
        with pytest.raises(DatabaseConfigurationError):
            validate_database_url(Environment.PROD, invalid)


def test_environment_failure_never_silently_downgrades_to_dev(monkeypatch):
    monkeypatch.setenv(ENVIRONMENT_ENV, Environment.PROD.value)
    monkeypatch.delenv(DATABASE_URL_ENV, raising=False)
    with pytest.raises(DatabaseConfigurationError):
        load_config()


def test_valid_prod_config_is_secret_safe_and_never_a_path(monkeypatch, tmp_path):
    url = f"sqlite:///{(tmp_path / 'prod.sqlite').as_posix()}"
    monkeypatch.setenv(DATABASE_URL_ENV, url)
    monkeypatch.setenv("HMS_QR_STORAGE_ROOT", "C:/hms-qr-production-storage")
    config = load_config(Environment.PROD)
    assert config.environment is Environment.PROD
    assert config.database_url == url
    assert "password" not in repr(config)
    assert "password" not in redacted_database_url(url)
    assert sqlite_path(url) == (tmp_path / "prod.sqlite").resolve()

    legacy = LEGACY_POSTGRESQL_URL
    password = make_url(legacy).password
    assert password
    assert password not in repr(AppConfig(Environment.PROD, legacy, "nas"))
    assert password not in redacted_database_url(legacy)
    with pytest.raises(DatabaseConfigurationError):
        sqlite_path(legacy)


def test_production_storage_root_must_be_ready_for_file_publication(tmp_path):
    missing = AppConfig(
        Environment.PROD,
        LEGACY_POSTGRESQL_URL,
        "nas",
        str(tmp_path / "missing-storage"),
    )
    with pytest.raises(Exception, match="HMS_QR_STORAGE_ROOT"):
        require_production_storage_ready(missing)

    ready_root = tmp_path / "ready-storage"
    ready_root.mkdir()
    ready = AppConfig(
        Environment.PROD,
        LEGACY_POSTGRESQL_URL,
        "nas",
        str(ready_root),
    )
    require_production_storage_ready(ready)
    assert not tuple(ready_root.rglob("*.probe"))


def test_production_database_schema_must_match_deployed_engine_head(tmp_path):
    from packages.sqlengine import Database

    with pytest.raises(DatabaseUnavailableError, match="schema is unavailable or uninitialized"):
        database = Database(tmp_path / "schema-empty-engine")
        try:
            require_database_schema_current(_prod_runtime(database))
        finally:
            database.close()

    database = Database(tmp_path / "schema-stale-engine")
    try:
        _stamp(database, [(1, "0001_stage2_baseline")])
        with pytest.raises(DatabaseUnavailableError, match="not at the deployed migration revision"):
            require_database_schema_current(_prod_runtime(database))
    finally:
        database.close()

    database = Database(tmp_path / "schema-current-engine")
    try:
        _stamp(database, [(7, "0007_server_accounts")])
        require_database_schema_current(_prod_runtime(database))
    finally:
        database.close()


def test_production_readiness_reports_stale_schema_without_hiding_database_state(tmp_path):
    from packages.sqlengine import Database

    database = Database(tmp_path / "readiness-engine")
    try:
        _stamp(database, [(1, "0001_stage2_baseline")])
        runtime = _prod_runtime(database)
        client = TestClient(build_api(app_config=runtime.config, database_runtime=runtime))
        response = client.get("/health/readiness/database")
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "DATABASE_SCHEMA_UNAVAILABLE"
    finally:
        database.close()


def test_engine_runtime_has_no_external_database_dependency():
    """The engine is in-process: no driver, no pool, no network database."""

    metadata = Path("pyproject.toml").read_text(encoding="utf-8")
    for forbidden in ("sqlalchemy", "alembic", "psycopg"):
        assert forbidden not in metadata
    requirements = Path("requirements.txt").read_text(encoding="utf-8")
    for forbidden in ("sqlalchemy", "alembic", "psycopg"):
        assert forbidden not in requirements


def test_shared_engine_is_one_database_for_every_repository(tmp_path):
    from packages.sqlengine import Database
    from packages.sqlengine.migrations import load_migration_modules, run_migrations
    from config.paths import SOURCE_ROOT

    database = Database(tmp_path / "shared-engine")
    try:
        run_migrations(
            database,
            load_migration_modules(SOURCE_ROOT / "migrations" / "engine"),
            now=lambda: "2026-01-01T00:00:00+00:00",
        )
        runtime = _prod_runtime(database)
        repositories = (
            Stage2Repository(runtime),
            TrackingRepository(runtime),
            WorkflowRepository(runtime),
            ManagedFileRepository(runtime),
            StoreForwardRepository(runtime),
            SqlAlchemyProductRepository(runtime),
        )
        assert all(repository.database is database for repository in repositories)
        assert database.readiness()["state"] == "READY"
    finally:
        database.close()


def test_session_scope_rolls_back_and_releases_on_exception(tmp_path):
    from packages.sqlengine import Database
    from packages.sqlengine.migrations import load_migration_modules, run_migrations
    from config.paths import SOURCE_ROOT

    database = Database(tmp_path / "rollback-engine")
    try:
        run_migrations(
            database,
            load_migration_modules(SOURCE_ROOT / "migrations" / "engine"),
            now=lambda: "2026-01-01T00:00:00+00:00",
        )
        marker = f"R010R2-ROLLBACK-{uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        with pytest.raises(RuntimeError, match="injected"):
            with session_scope(_prod_runtime(database)) as transaction:
                transaction.execute(
                    "INSERT INTO products (internal_id, product_code, company, part_name, "
                    "quantity, unit, outsourced, status, created_at, updated_at, "
                    "created_by, updated_by) VALUES (?, ?, 'HMS', 'Rollback', ?, 'pcs', 0, "
                    "'NEW', ?, ?, 'test', 'test')",
                    [str(uuid4()), marker, Decimal("1.0000"), now, now],
                )
                raise RuntimeError("injected transaction failure")
        assert database.query(
            "SELECT internal_id FROM products WHERE product_code = ?", [marker]
        ) == []
    finally:
        database.close()


def test_product_master_engine_api_and_type_round_trip(tmp_path, monkeypatch):
    from packages.sqlengine import Database
    from packages.sqlengine.migrations import load_migration_modules, run_migrations
    from config.paths import SOURCE_ROOT

    database = Database(tmp_path / "product-engine")
    try:
        run_migrations(
            database,
            load_migration_modules(SOURCE_ROOT / "migrations" / "engine"),
            now=lambda: "2026-01-01T00:00:00+00:00",
        )
        code = f"R010R2-ENGINE-{uuid4().hex[:8].upper()}"
        monkeypatch.setenv("HMS_QR_AUTH_SECRET", "r010r2-engine-acceptance-token-secret")
        runtime = _prod_runtime(database)
        auth = ServerAuthService(runtime)
        username = f"r010r2-editor-{uuid4().hex[:8]}"
        auth.create_account(username, "acceptance-password", UserRole.EDITOR.value)
        token = auth.login(username, "acceptance-password")["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        with TestClient(build_api(app_config=runtime.config, database_runtime=runtime)) as client:
            created = client.post(
                "/api/v1/products",
                headers=headers,
                json={
                    "product_code": code,
                    "company": "HMS",
                    "part_name": "Engine Plate",
                    "quantity": "12.3400",
                    "unit": "pcs",
                    "outsourced": True,
                },
            )
            assert created.status_code == 201
            body = created.json()
            assert client.get(f"/api/v1/products/{body['internal_id']}").status_code == 200
            patched = client.patch(
                f"/api/v1/products/{body['internal_id']}",
                headers=headers,
                json={"status": "IN_PROGRESS", "expected_updated_at": body["updated_at"]},
            )
            assert patched.status_code == 200
            assert client.get(
                "/api/v1/products", headers=headers, params={"search": code}
            ).json()["total"] == 1
            assert client.get("/health/readiness/database").status_code == 200

        repository = SqlAlchemyProductRepository(runtime)
        product = repository.get_by_code(code)
        assert product.quantity == Decimal("12.3400")
        assert product.outsourced is True
        assert product.created_at.utcoffset().total_seconds() == 0
        assert product.updated_at.utcoffset().total_seconds() == 0
    finally:
        database.close()


def test_two_editor_sessions_receive_product_conflict_for_stale_engine_write(tmp_path, monkeypatch):
    from packages.sqlengine import Database
    from packages.sqlengine.migrations import load_migration_modules, run_migrations
    from config.paths import SOURCE_ROOT

    database = Database(tmp_path / "conflict-engine")
    try:
        run_migrations(
            database,
            load_migration_modules(SOURCE_ROOT / "migrations" / "engine"),
            now=lambda: "2026-01-01T00:00:00+00:00",
        )
        monkeypatch.setenv("HMS_QR_AUTH_SECRET", "r010r2-engine-conflict-token-secret")
        runtime = _prod_runtime(database)
        auth = ServerAuthService(runtime)
        tokens = []
        for label in ("one", "two"):
            username = f"r010r2-conflict-{label}-{uuid4().hex[:8]}"
            auth.create_account(username, "acceptance-password", UserRole.EDITOR.value)
            tokens.append(auth.login(username, "acceptance-password")["access_token"])
        first_headers, second_headers = ({"Authorization": f"Bearer {token}"} for token in tokens)
        with TestClient(build_api(app_config=runtime.config, database_runtime=runtime)) as client:
            created = client.post("/api/v1/products", headers=first_headers, json={
                "product_code": f"R010R2-CONFLICT-{uuid4().hex[:8].upper()}", "company": "HMS",
                "part_name": "Concurrent Plate", "quantity": "1", "unit": "pcs", "outsourced": False,
            })
            assert created.status_code == 201
            product = created.json()
            first_loaded = client.get(
                f"/api/v1/products/{product['internal_id']}", headers=first_headers
            ).json()
            second_loaded = client.get(
                f"/api/v1/products/{product['internal_id']}", headers=second_headers
            ).json()
            first_write = client.patch(
                f"/api/v1/products/{product['internal_id']}", headers=first_headers, json={
                    "notes": "editor one", "expected_updated_at": first_loaded["updated_at"],
                }
            )
            stale_write = client.patch(
                f"/api/v1/products/{product['internal_id']}", headers=second_headers, json={
                    "notes": "editor two", "expected_updated_at": second_loaded["updated_at"],
                }
            )
        assert first_write.status_code == 200
        assert stale_write.status_code == 409
        assert stale_write.json()["error"]["code"] == "PRODUCT_CONFLICT"
    finally:
        database.close()
