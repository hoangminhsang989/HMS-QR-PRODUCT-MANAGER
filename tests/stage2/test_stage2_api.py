from datetime import date, datetime, timezone
from uuid import UUID
from fastapi.testclient import TestClient
from packages.persistence.stage2_repository import Stage2Repository
from packages.domain.product import Product, ProductStatus
from packages.persistence.engine_product_repository import EngineProductRepository
from packages.application.stage2_service import Stage2Service
from packages.application.server_auth import ServerAuthService, UserRole
from packages.persistence.database import create_database_runtime_for_url
from apps.server.app import build_stage2_api

def test_stage2_api_customer_po_line_schedule_run(tmp_path):
    repo=Stage2Repository(f"sqlite:///{(tmp_path/'api.sqlite').as_posix()}"); repo.create_schema(); pid="00000000-0000-0000-0000-000000000001"
    EngineProductRepository(repo.database).create(Product(internal_id=UUID(pid),product_code="SP-API",company="HMS",part_name="Plate",quantity=100,unit="pcs",material=None,requester=None,surface_treatment=None,outsourced=False,size=None,notes=None,delivery_schedule=None,status=ProductStatus.NEW,created_at=datetime.now(timezone.utc),updated_at=datetime.now(timezone.utc),created_by="seed",updated_by="seed"))
    client=TestClient(build_stage2_api(Stage2Service(repo)))
    c=client.post("/api/v1/customers",json={"name":"HMS"},headers={"X-Actor":"api"}); assert c.status_code==200; customer=c.json()
    duplicate_customer=client.post("/api/v1/customers",json={"customer_code":customer["customer_code"],"name":"Other"}); assert duplicate_customer.status_code in (400,409,500)
    po=client.post("/api/v1/purchase-orders",json={"po_number":"PO-API","customer_id":customer["internal_id"],"po_date":"2026-08-01"}); assert po.status_code==200
    line=client.post(f"/api/v1/purchase-orders/{po.json()['internal_id']}/lines",json={"product_id":pid,"line_number":1,"ordered_quantity":100,"unit":"pcs"}); assert line.status_code==200
    lid=line.json()["internal_id"]
    delivery=client.post(f"/api/v1/purchase-order-lines/{lid}/delivery-schedules?ordered_quantity=100",json={"planned_date":"2026-08-20","planned_quantity":50}); assert delivery.status_code==200
    updated=client.patch(f"/api/v1/delivery-schedule-entries/{delivery.json()['internal_id']}?po_line_id={lid}&ordered_quantity=100",json={"planned_date":"2026-08-21","planned_quantity":50,"notes":"Đổi lịch"}); assert updated.status_code==200 and updated.json()["planned_date"]=="2026-08-21"
    run=client.post("/api/v1/production-runs",json={"po_line_id":lid,"product_id":pid,"ordered_quantity":100,"planned_quantity":50}); assert run.status_code==200
    assert client.get("/api/v1/production-runs",params={"po_line_id":lid}).json()["items"]
    assert client.patch(f"/api/v1/production-runs/{run.json()['internal_id']}?ordered_quantity=100",json={"po_line_id":lid,"product_id":pid,"ordered_quantity":100,"planned_quantity":50,"completed_quantity":10}).status_code == 200


def test_stage2_api_uses_central_session_roles(tmp_path, monkeypatch):
    monkeypatch.setenv("HMS_QR_AUTH_SECRET", "s" * 32)
    runtime = create_database_runtime_for_url(f"sqlite:///{(tmp_path/'secured.sqlite').as_posix()}")
    Stage2Repository(runtime).create_schema()
    auth = ServerAuthService(runtime)
    auth.create_account("editor", "editor-password", UserRole.EDITOR.value)
    auth.create_account("viewer", "viewer-password", UserRole.VIEWER.value)
    editor = auth.login("editor", "editor-password")["access_token"]
    viewer = auth.login("viewer", "viewer-password")["access_token"]
    client = TestClient(build_stage2_api(database_runtime=runtime))
    assert client.get("/api/v1/customers").status_code == 401
    assert client.post("/api/v1/customers", json={"name": "Blocked"}, headers={"Authorization": f"Bearer {viewer}"}).status_code == 403
    created = client.post("/api/v1/customers", json={"name": "Allowed"}, headers={"Authorization": f"Bearer {editor}"})
    assert created.status_code == 200
    assert client.get("/api/v1/customers", headers={"Authorization": f"Bearer {viewer}"}).json()["total"] == 1
    payload = {"po_number": "SESSION-PO", "customer_id": created.json()["internal_id"], "po_date": "2026-09-20"}
    assert client.post("/api/v1/purchase-orders", json=payload, headers={"Authorization": f"Bearer {viewer}"}).status_code == 403
    assert client.post("/api/v1/purchase-orders", json=payload, headers={"Authorization": f"Bearer {editor}"}).status_code == 200
