"""R010R2 production database configuration and PostgreSQL runtime acceptance."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select, text

from apps.server.app import build_api
from apps.server.files import require_production_storage_ready
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
    DatabaseUnavailableError,
    create_database_runtime,
    redacted_database_url,
    require_database_schema_current,
    session_scope,
    sqlite_path,
)
from packages.persistence.managed_file_repository import ManagedFileRepository
from packages.persistence.sqlalchemy_models import ProductORM
from packages.persistence.sqlalchemy_product_repository import SqlAlchemyProductRepository
from packages.persistence.sqlalchemy_repository import Stage2Repository
from packages.persistence.store_forward_repository import StoreForwardRepository
from packages.persistence.tracking_repository import TrackingRepository
from packages.persistence.workflow_repository import WorkflowRepository
from packages.application.server_auth import ServerAuthService, UserRole


def _postgresql_url() -> str:
    value = (
        os.environ.get("HMS_QR_R010R2_POSTGRESQL_URL", "").strip()
        or os.environ.get("HMS_QR_R010M1_POSTGRESQL_URL", "").strip()
    )
    if not value:
        pytest.skip("isolated R010R2 PostgreSQL runtime is not configured")
    return value


def _reset_and_upgrade(url: str) -> None:
    runtime = create_database_runtime(AppConfig(Environment.PROD, url, "test"))
    with runtime.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
        connection.exec_driver_sql("CREATE SCHEMA public")
    runtime.dispose()
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")


@pytest.fixture(scope="module")
def pg_runtime():
    url = _postgresql_url()
    _reset_and_upgrade(url)
    runtime = create_database_runtime(AppConfig(Environment.PROD, url, "configured"))
    yield runtime
    runtime.dispose()


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


def test_valid_prod_config_is_secret_safe_and_never_a_path(monkeypatch):
    url = _postgresql_url()
    monkeypatch.setenv(DATABASE_URL_ENV, url)
    monkeypatch.setenv("HMS_QR_STORAGE_ROOT", "C:/hms-qr-production-storage")
    config = load_config(Environment.PROD)
    password = __import__("sqlalchemy").engine.make_url(url).password
    assert config.environment is Environment.PROD
    assert config.database_url == url
    assert password not in repr(config)
    assert password not in redacted_database_url(url)
    with pytest.raises(DatabaseConfigurationError):
        sqlite_path(url)


def test_production_storage_root_must_be_ready_for_file_publication(tmp_path):
    missing = AppConfig(
        Environment.PROD,
        "postgresql+psycopg://user:password@localhost/hms_qr",
        "nas",
        str(tmp_path / "missing-storage"),
    )
    with pytest.raises(Exception, match="HMS_QR_STORAGE_ROOT"):
        require_production_storage_ready(missing)

    ready_root = tmp_path / "ready-storage"
    ready_root.mkdir()
    ready = AppConfig(
        Environment.PROD,
        "postgresql+psycopg://user:password@localhost/hms_qr",
        "nas",
        str(ready_root),
    )
    require_production_storage_ready(ready)
    assert not tuple(ready_root.rglob("*.probe"))


def test_production_database_schema_must_match_deployed_alembic_head(tmp_path):
    config = AppConfig(
        Environment.DEV, f"sqlite:///{(tmp_path / 'schema.sqlite').as_posix()}", "local"
    )
    local = create_database_runtime(config)
    production = type(local)(
        AppConfig(Environment.PROD, "postgresql+psycopg://user:password@localhost/hms_qr", "nas"),
        local.engine,
        local.session_factory,
    )
    with pytest.raises(DatabaseUnavailableError, match="schema is unavailable or uninitialized"):
        require_database_schema_current(production)

    local = create_database_runtime(config)
    with local.engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0001_stage2_baseline')"))
    production = type(local)(
        AppConfig(Environment.PROD, "postgresql+psycopg://user:password@localhost/hms_qr", "nas"),
        local.engine,
        local.session_factory,
    )
    with pytest.raises(DatabaseUnavailableError, match="not at the deployed migration revision"):
        require_database_schema_current(production)

    local = create_database_runtime(config)
    with local.engine.begin() as connection:
        connection.execute(text("DELETE FROM alembic_version"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0007_server_accounts')"))
    production = type(local)(
        AppConfig(Environment.PROD, "postgresql+psycopg://user:password@localhost/hms_qr", "nas"),
        local.engine,
        local.session_factory,
    )
    require_database_schema_current(production)
    production.dispose()


def test_production_readiness_reports_stale_schema_without_hiding_database_state(tmp_path):
    config = AppConfig(
        Environment.DEV, f"sqlite:///{(tmp_path / 'readiness.sqlite').as_posix()}", "local"
    )
    local = create_database_runtime(config)
    with local.engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0001_stage2_baseline')"))
    runtime = type(local)(
        AppConfig(Environment.PROD, "postgresql+psycopg://user:password@localhost/hms_qr", "nas"),
        local.engine,
        local.session_factory,
    )
    client = TestClient(build_api(app_config=runtime.config, database_runtime=runtime))
    response = client.get("/health/readiness/database")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "DATABASE_SCHEMA_UNAVAILABLE"
    runtime.dispose()


def test_tracked_psycopg_dependency_is_canonical_metadata():
    metadata = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "psycopg[binary]" in metadata
    assert "postgres:latest" not in metadata


def test_shared_engine_session_pool_and_readiness(pg_runtime):
    assert pg_runtime.readiness() == {"state": "READY", "database": "prod"}
    pool = pg_runtime.engine.pool
    assert pool.size() == 5
    assert pool._max_overflow == 5
    assert pool._timeout == 30
    assert pool._pre_ping is True

    repositories = (
        Stage2Repository(pg_runtime),
        TrackingRepository(pg_runtime),
        WorkflowRepository(pg_runtime),
        ManagedFileRepository(pg_runtime),
        StoreForwardRepository(pg_runtime),
        SqlAlchemyProductRepository(pg_runtime),
    )
    assert all(repository.engine is pg_runtime.engine for repository in repositories)
    assert all(repository.Session is pg_runtime.session_factory for repository in repositories)


def test_session_scope_rolls_back_and_releases_on_exception(pg_runtime):
    marker = f"R010R2-ROLLBACK-{uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    with pytest.raises(RuntimeError, match="injected"):
        with session_scope(pg_runtime) as session:
            session.add(ProductORM(
                internal_id=str(uuid4()), product_code=marker, company="HMS",
                part_name="Rollback", quantity=Decimal("1.0000"), unit="pcs",
                material=None, requester=None, surface_treatment=None,
                outsourced=False, size=None, notes=None, delivery_schedule=None,
                status="NEW", created_at=now, updated_at=now,
                created_by="test", updated_by="test",
            ))
            raise RuntimeError("injected transaction failure")
    with pg_runtime.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ProductORM).where(
            ProductORM.product_code == marker
        )) == 0


def test_product_master_postgresql_api_and_type_utc_round_trip(pg_runtime, monkeypatch):
    code = f"R010R2-PG-{uuid4().hex[:8].upper()}"
    config = AppConfig(Environment.PROD, _postgresql_url(), "configured")
    username = f"r010r2-editor-{uuid4().hex[:8]}"
    monkeypatch.setenv("HMS_QR_AUTH_SECRET", "r010r2-postgresql-acceptance-token-secret")
    auth = ServerAuthService(pg_runtime)
    auth.create_account(username, "acceptance-password", UserRole.EDITOR.value)
    token = auth.login(username, "acceptance-password")["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(build_api(app_config=config, database_runtime=pg_runtime)) as client:
        created = client.post(
            "/api/v1/products",
            headers=headers,
            json={
                "product_code": code,
                "company": "HMS",
                "part_name": "PostgreSQL Plate",
                "quantity": "12.3400",
                "unit": "pcs",
                "outsourced": True,
            },
        )
        assert created.status_code == 201
        body = created.json()
        fetched = client.get(f"/api/v1/products/{body['internal_id']}")
        assert fetched.status_code == 200
        patched = client.patch(
            f"/api/v1/products/{body['internal_id']}",
            headers=headers,
            json={"status": "IN_PROGRESS", "expected_updated_at": body["updated_at"]},
        )
        assert patched.status_code == 200
        assert client.get("/api/v1/products", headers=headers, params={"search": code}).json()["total"] == 1
        readiness = client.get("/health/readiness/database")
        assert readiness.status_code == 200
        assert readiness.json()["state"] == "READY"

    repository = SqlAlchemyProductRepository(pg_runtime)
    product = repository.get_by_code(code)
    assert product.quantity == Decimal("12.3400")
    assert product.outsourced is True
    assert product.created_at.utcoffset().total_seconds() == 0
    assert product.updated_at.utcoffset().total_seconds() == 0


def test_two_editor_sessions_receive_product_conflict_for_stale_postgresql_write(pg_runtime, monkeypatch):
    config = AppConfig(Environment.PROD, _postgresql_url(), "configured")
    monkeypatch.setenv("HMS_QR_AUTH_SECRET", "r010r2-postgresql-acceptance-token-secret")
    auth = ServerAuthService(pg_runtime)
    tokens = []
    for label in ("one", "two"):
        username = f"r010r2-conflict-{label}-{uuid4().hex[:8]}"
        auth.create_account(username, "acceptance-password", UserRole.EDITOR.value)
        tokens.append(auth.login(username, "acceptance-password")["access_token"])
    first_headers, second_headers = ({"Authorization": f"Bearer {token}"} for token in tokens)
    with TestClient(build_api(app_config=config, database_runtime=pg_runtime)) as client:
        created = client.post("/api/v1/products", headers=first_headers, json={
            "product_code": f"R010R2-CONFLICT-{uuid4().hex[:8].upper()}", "company": "HMS",
            "part_name": "Concurrent Plate", "quantity": "1", "unit": "pcs", "outsourced": False,
        })
        assert created.status_code == 201
        product = created.json()
        first_loaded = client.get(f"/api/v1/products/{product['internal_id']}", headers=first_headers).json()
        second_loaded = client.get(f"/api/v1/products/{product['internal_id']}", headers=second_headers).json()
        first_write = client.patch(f"/api/v1/products/{product['internal_id']}", headers=first_headers, json={
            "notes": "editor one", "expected_updated_at": first_loaded["updated_at"],
        })
        stale_write = client.patch(f"/api/v1/products/{product['internal_id']}", headers=second_headers, json={
            "notes": "editor two", "expected_updated_at": second_loaded["updated_at"],
        })
    assert first_write.status_code == 200
    assert stale_write.status_code == 409
    assert stale_write.json()["error"]["code"] == "PRODUCT_CONFLICT"


def test_real_runtime_outage_and_pool_recovery(pg_runtime):
    container = os.environ.get("HMS_QR_R010R2_CONTAINER", "").strip()
    if not container:
        pytest.skip("dedicated R010R2 container identity is not configured")
    try:
        stopped = subprocess.run(
            ["docker", "stop", "--time", "5", container],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        assert stopped.returncode == 0
        assert pg_runtime.readiness()["state"] == "UNAVAILABLE"
    finally:
        started = subprocess.run(
            ["docker", "start", container],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        assert started.returncode == 0

    for _ in range(30):
        if pg_runtime.readiness()["state"] == "READY":
            break
        time.sleep(1)
    assert pg_runtime.readiness()["state"] == "READY"
    with pg_runtime.engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT 1").scalar_one() == 1
