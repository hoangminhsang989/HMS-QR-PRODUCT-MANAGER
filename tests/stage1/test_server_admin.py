from fastapi.testclient import TestClient
import pytest

from apps.server.admin import admin_page, build_admin_api
from config.environments import AppConfig, Environment
from packages.application.server_auth import AuthenticationError, ServerAuthService
from packages.persistence.database import create_database_runtime
from packages.persistence.sqlalchemy_repository import Stage2Repository


def test_server_admin_bootstraps_accounts_and_restricts_admin_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("HMS_QR_BOOTSTRAP_ADMIN_USERNAME", "server-admin")
    monkeypatch.setenv("HMS_QR_BOOTSTRAP_ADMIN_PASSWORD", "secure-password-123")
    monkeypatch.setenv("HMS_QR_AUTH_SECRET", "test-signing-secret")
    config = AppConfig(Environment.DEV, f"sqlite:///{(tmp_path / 'admin.sqlite').as_posix()}", "local")
    runtime = create_database_runtime(config)
    Stage2Repository(runtime).create_schema()
    client = TestClient(build_admin_api(config, runtime))
    denied = client.get("/api/v1/admin/accounts")
    login = client.post("/api/v1/auth/login", json={"username": "server-admin", "password": "secure-password-123"})
    assert denied.status_code == 401
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post("/api/v1/admin/accounts", headers=headers, json={
        "username": "lan-editor", "password": "another-password-123", "role": "EDITOR",
    })
    assert created.status_code == 200
    assert client.get("/api/v1/admin/accounts", headers=headers).json()["items"][1]["username"] == "server-admin"
    updated = client.put("/api/v1/admin/settings", headers=headers, json={"site_title": "Xuong HMS"})
    assert updated.json()["site_title"] == "Xuong HMS"
    assert "HMS QR Server" in admin_page().body.decode("utf-8")
    runtime.dispose()


def test_server_admin_allows_empty_password_only_when_explicitly_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("HMS_QR_BOOTSTRAP_ADMIN_USERNAME", "server-admin")
    monkeypatch.setenv("HMS_QR_BOOTSTRAP_ADMIN_PASSWORD", "")
    monkeypatch.setenv("HMS_QR_AUTH_SECRET", "test-signing-secret")
    monkeypatch.setenv("HMS_QR_ALLOW_EMPTY_PASSWORDS", "true")
    config = AppConfig(Environment.DEV, f"sqlite:///{(tmp_path / 'empty-password.sqlite').as_posix()}", "local")
    runtime = create_database_runtime(config)
    Stage2Repository(runtime).create_schema()
    client = TestClient(build_admin_api(config, runtime))
    login = client.post("/api/v1/auth/login", json={"username": "server-admin", "password": ""})
    assert login.status_code == 200
    runtime.dispose()


def test_server_admin_accepts_three_character_passwords(tmp_path, monkeypatch):
    monkeypatch.setenv("HMS_QR_BOOTSTRAP_ADMIN_USERNAME", "server-admin")
    monkeypatch.setenv("HMS_QR_BOOTSTRAP_ADMIN_PASSWORD", "abc")
    monkeypatch.setenv("HMS_QR_AUTH_SECRET", "test-signing-secret")
    config = AppConfig(Environment.DEV, f"sqlite:///{(tmp_path / 'short-password.sqlite').as_posix()}", "local")
    runtime = create_database_runtime(config)
    Stage2Repository(runtime).create_schema()
    client = TestClient(build_admin_api(config, runtime))
    assert client.post("/api/v1/auth/login", json={"username": "server-admin", "password": "abc"}).status_code == 200
    runtime.dispose()


def test_production_auth_configuration_requires_secret_and_disallows_empty_passwords(tmp_path, monkeypatch):
    local = create_database_runtime(AppConfig(Environment.DEV, f"sqlite:///{(tmp_path / 'auth.sqlite').as_posix()}", "local"))
    config = AppConfig(Environment.PROD, "postgresql+psycopg://user:password@localhost/hms_qr", "nas", "C:/hms-qr-files")
    runtime = type(local)(config, local.engine, local.session_factory)
    monkeypatch.setenv("HMS_QR_AUTH_SECRET", "too-short")
    with pytest.raises(AuthenticationError, match="HMS_QR_AUTH_SECRET"):
        ServerAuthService(runtime).require_production_configuration()
    monkeypatch.setenv("HMS_QR_AUTH_SECRET", "x" * 32)
    monkeypatch.setenv("HMS_QR_ALLOW_EMPTY_PASSWORDS", "true")
    with pytest.raises(AuthenticationError, match="Empty passwords"):
        ServerAuthService(runtime).require_production_configuration()
    runtime.dispose()


def test_first_production_account_requires_bootstrap_credentials(tmp_path, monkeypatch):
    config = AppConfig(
        Environment.DEV, f"sqlite:///{(tmp_path / 'bootstrap.sqlite').as_posix()}", "local"
    )
    local = create_database_runtime(config)
    Stage2Repository(local).create_schema()
    runtime = type(local)(
        AppConfig(Environment.PROD, "postgresql+psycopg://user:password@localhost/hms_qr", "nas"),
        local.engine,
        local.session_factory,
    )
    monkeypatch.delenv("HMS_QR_BOOTSTRAP_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("HMS_QR_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    with pytest.raises(AuthenticationError, match="no administrator account"):
        ServerAuthService(runtime).bootstrap_admin()
    monkeypatch.setenv("HMS_QR_BOOTSTRAP_ADMIN_USERNAME", "server-admin")
    monkeypatch.setenv("HMS_QR_BOOTSTRAP_ADMIN_PASSWORD", "secure-password-123")
    ServerAuthService(runtime).bootstrap_admin()
    assert ServerAuthService(runtime).list_accounts()[0]["username"] == "server-admin"
    runtime.dispose()


def test_existing_bearer_token_uses_current_account_state(tmp_path, monkeypatch):
    monkeypatch.setenv("HMS_QR_AUTH_SECRET", "test-signing-secret")
    config = AppConfig(Environment.DEV, f"sqlite:///{(tmp_path / 'sessions.sqlite').as_posix()}", "local")
    runtime = create_database_runtime(config)
    Stage2Repository(runtime).create_schema()
    auth = ServerAuthService(runtime)
    account = auth.create_account("lan-editor", "secure-password-123", "EDITOR")
    token = auth.login("lan-editor", "secure-password-123")["access_token"]
    assert auth.authenticate(token)["role"] == "EDITOR"
    auth.update_account(account["internal_id"], role="VIEWER")
    assert auth.authenticate(token)["role"] == "VIEWER"
    auth.update_account(account["internal_id"], active=False)
    with pytest.raises(AuthenticationError, match="không còn hoạt động"):
        auth.authenticate(token)
    runtime.dispose()


def test_last_active_administrator_cannot_be_disabled_or_demoted(tmp_path, monkeypatch):
    monkeypatch.setenv("HMS_QR_AUTH_SECRET", "test-signing-secret")
    config = AppConfig(Environment.DEV, f"sqlite:///{(tmp_path / 'admins.sqlite').as_posix()}", "local")
    runtime = create_database_runtime(config)
    Stage2Repository(runtime).create_schema()
    auth = ServerAuthService(runtime)
    first = auth.create_account("admin-one", "secure-password-123", "ADMIN")
    with pytest.raises(ValueError, match="quản trị viên cuối cùng"):
        auth.update_account(first["internal_id"], active=False)
    with pytest.raises(ValueError, match="quản trị viên cuối cùng"):
        auth.update_account(first["internal_id"], role="EDITOR")
    auth.create_account("admin-two", "secure-password-123", "ADMIN")
    assert auth.update_account(first["internal_id"], role="EDITOR")["role"] == "EDITOR"
    runtime.dispose()


def test_administrator_can_reset_account_password_without_exposing_it(tmp_path, monkeypatch):
    monkeypatch.setenv("HMS_QR_AUTH_SECRET", "test-signing-secret")
    config = AppConfig(Environment.DEV, f"sqlite:///{(tmp_path / 'password-reset.sqlite').as_posix()}", "local")
    runtime = create_database_runtime(config)
    Stage2Repository(runtime).create_schema()
    auth = ServerAuthService(runtime)
    account = auth.create_account("lan-editor", "old-password-123", "EDITOR")

    updated = auth.update_account(account["internal_id"], password="new-password-456")

    assert "password" not in updated
    with pytest.raises(AuthenticationError):
        auth.login("lan-editor", "old-password-123")
    assert auth.login("lan-editor", "new-password-456")["username"] == "lan-editor"
    runtime.dispose()


def test_administrator_can_rename_account_without_changing_its_internal_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("HMS_QR_AUTH_SECRET", "test-signing-secret")
    config = AppConfig(Environment.DEV, f"sqlite:///{(tmp_path / 'rename-account.sqlite').as_posix()}", "local")
    runtime = create_database_runtime(config)
    Stage2Repository(runtime).create_schema()
    auth = ServerAuthService(runtime)
    account = auth.create_account("lan-editor", "secure-password-123", "EDITOR")

    updated = auth.update_account(account["internal_id"], username="lan-editor-new")

    assert updated["internal_id"] == account["internal_id"]
    assert auth.login("lan-editor-new", "secure-password-123")["username"] == "lan-editor-new"
    runtime.dispose()
