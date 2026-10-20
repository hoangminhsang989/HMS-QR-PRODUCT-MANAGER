from fastapi.testclient import TestClient
from fastapi import HTTPException
import pytest

from apps.server.app import build_api, build_tracking_api, require_sqlite_legacy_endpoint
from config.environments import AppConfig, Environment
from packages.application.server_auth import ServerAuthService
from packages.application.product_service import ProductService
from packages.persistence.database import create_database_runtime
from packages.persistence.sqlite_product_repository import SQLiteProductRepository
from packages.persistence.sqlalchemy_repository import Stage2Repository
from packages.persistence.tracking_repository import TrackingRepository
from packages.application.tracking_service import TrackingService


def test_api_create_read_patch_list_search_filter(tmp_path):
    service = ProductService(SQLiteProductRepository(tmp_path / "api.sqlite"))
    client = TestClient(build_api(service))
    response = client.post("/api/v1/products", headers={"X-Actor": "api-user"}, json={
        "company": "HMS", "part_name": "Plate", "quantity": 4, "unit": "pcs", "material": "Al",
    })
    assert response.status_code == 201
    created = response.json()
    assert created["created_by"] == "api-user"
    assert client.get(f"/api/v1/products/{created['product_code']}").status_code == 200
    patched = client.patch(f"/api/v1/products/{created['internal_id']}", headers={"X-Actor": "editor"}, json={"status": "IN_PROGRESS"})
    assert patched.status_code == 200
    assert client.get("/api/v1/products", params={"search": "plate", "status": "IN_PROGRESS"}).json()["total"] == 1
    assert client.get("/api/v1/products/nope").status_code == 404
    duplicate = client.post("/api/v1/products", json={"product_code": created["product_code"], "company": "HMS", "part_name": "x", "quantity": 1, "unit": "pcs"})
    assert duplicate.status_code == 409


def test_api_product_patch_code_and_delivery_range(tmp_path):
    service = ProductService(SQLiteProductRepository(tmp_path / "api-range.sqlite"))
    client = TestClient(build_api(service))
    created = client.post("/api/v1/products", headers={"X-Actor": "api-user"}, json={
        "product_code": "before", "company": "HMS", "part_name": "Plate", "quantity": 4,
        "unit": "pcs", "delivery_schedule": "2026-09-19",
    }).json()
    patched = client.patch(
        f"/api/v1/products/{created['internal_id']}", headers={"X-Actor": "editor"},
        json={"product_code": "after"},
    )
    assert patched.status_code == 200
    assert patched.json()["product_code"] == "AFTER"
    result = client.get("/api/v1/products", params={
        "delivery_start": "2026-09-01", "delivery_end": "2026-10-01",
    }).json()
    assert [item["product_code"] for item in result["items"]] == ["AFTER"]


def test_api_accepts_blank_customer_and_zero_quantity(tmp_path):
    client = TestClient(build_api(ProductService(SQLiteProductRepository(tmp_path / "api-incomplete.sqlite"))))

    response = client.post("/api/v1/products", headers={"X-Actor": "api-user"}, json={
        "company": "", "part_name": "", "quantity": 0, "unit": "pcs",
    })

    assert response.status_code == 201
    assert response.json()["company"] == ""
    assert response.json()["quantity"] == "0"


def test_runtime_product_api_requires_account_roles(tmp_path, monkeypatch):
    monkeypatch.setenv("HMS_QR_BOOTSTRAP_ADMIN_USERNAME", "server-admin")
    monkeypatch.setenv("HMS_QR_BOOTSTRAP_ADMIN_PASSWORD", "secure-password-123")
    monkeypatch.setenv("HMS_QR_AUTH_SECRET", "test-signing-secret")
    config = AppConfig(Environment.DEV, f"sqlite:///{(tmp_path / 'roles.sqlite').as_posix()}", "local")
    runtime = create_database_runtime(config)
    Stage2Repository(runtime).create_schema()
    auth = ServerAuthService(runtime)
    auth.bootstrap_admin()
    auth.create_account("lan-viewer", "viewer-password-123", "VIEWER")
    auth.create_account("lan-editor", "editor-password-123", "EDITOR")
    service = ProductService(SQLiteProductRepository(tmp_path / "isolated-products.sqlite"))
    client = TestClient(build_api(service, app_config=config, database_runtime=runtime))
    viewer_token = auth.login("lan-viewer", "viewer-password-123")["access_token"]
    editor_token = auth.login("lan-editor", "editor-password-123")["access_token"]
    payload = {"company": "HMS", "part_name": "Plate", "quantity": 4, "unit": "pcs"}
    assert client.post("/api/v1/products", json=payload).status_code == 401
    assert client.post("/api/v1/products", headers={"Authorization": f"Bearer {viewer_token}"}, json=payload).status_code == 403
    created = client.post("/api/v1/products", headers={"Authorization": f"Bearer {editor_token}"}, json=payload)
    assert created.status_code == 201
    assert created.json()["created_by"] == "lan-editor"
    assert client.get("/api/v1/products", headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 200
    assert client.patch(f"/api/v1/products/{created.json()['internal_id']}", headers={"Authorization": f"Bearer {editor_token}"}, json={"status": "IN_PROGRESS"}).status_code == 422
    changed = client.patch(f"/api/v1/products/{created.json()['internal_id']}", headers={"Authorization": f"Bearer {editor_token}"}, json={"status": "IN_PROGRESS", "expected_updated_at": created.json()["updated_at"]})
    assert changed.status_code == 200
    stale = client.patch(f"/api/v1/products/{created.json()['internal_id']}", headers={"Authorization": f"Bearer {editor_token}"}, json={"status": "HOLD", "expected_updated_at": created.json()["updated_at"]})
    assert stale.status_code == 409
    runtime.dispose()


def test_runtime_tracking_api_requires_lan_account_roles(tmp_path, monkeypatch):
    monkeypatch.setenv("HMS_QR_BOOTSTRAP_ADMIN_USERNAME", "server-admin")
    monkeypatch.setenv("HMS_QR_BOOTSTRAP_ADMIN_PASSWORD", "abc")
    monkeypatch.setenv("HMS_QR_AUTH_SECRET", "test-signing-secret")
    config = AppConfig(Environment.DEV, f"sqlite:///{(tmp_path / 'tracking-roles.sqlite').as_posix()}", "local")
    runtime = create_database_runtime(config)
    Stage2Repository(runtime).create_schema()
    auth = ServerAuthService(runtime)
    auth.bootstrap_admin()
    auth.create_account("lan-viewer", "abc", "VIEWER")
    viewer_token = auth.login("lan-viewer", "abc")["access_token"]
    client = TestClient(build_tracking_api(TrackingService(TrackingRepository(runtime)), app_config=config, database_runtime=runtime))
    assert client.get("/api/v1/tracking-items").status_code == 401
    assert client.get("/api/v1/tracking-items", headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 200
    assert client.post("/api/v1/operators", headers={"Authorization": f"Bearer {viewer_token}"}, json={"display_name": "Viewer"}).status_code == 403
    runtime.dispose()


def test_sqlite_legacy_portal_endpoints_are_rejected_outside_dev():
    config = AppConfig(Environment.PROD, "postgresql+psycopg://user:password@localhost/hms_qr", "nas")
    with pytest.raises(HTTPException) as exc:
        require_sqlite_legacy_endpoint(config)
    assert exc.value.status_code == 501
    assert exc.value.detail["code"] == "SQLITE_LEGACY_ENDPOINT_UNSUPPORTED"


def test_the_legacy_gate_does_not_blame_a_database_that_is_gone():
    """The 501 message blamed PostgreSQL, which the engine cutover removed.

    An operator who met that message went looking for a PostgreSQL problem
    that does not exist. The gate is a DEV-only restriction; say so.
    """
    config = AppConfig(Environment.PROD, "postgresql+psycopg://user:password@localhost/hms_qr", "nas")
    with pytest.raises(HTTPException) as exc:
        require_sqlite_legacy_endpoint(config)
    message = exc.value.detail["message"]
    assert "PostgreSQL" not in message
    assert "DEV" in message
