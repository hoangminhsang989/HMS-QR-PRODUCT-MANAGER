from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from packages.persistence.sqlalchemy_repository import Stage2Repository
from packages.persistence.sqlalchemy_models import ProductORM
from packages.application.stage2_service import Stage2Service
from apps.server.app import build_stage2_api

def test_stage2_api_customer_po_line_schedule_run(tmp_path):
    repo=Stage2Repository(f"sqlite:///{(tmp_path/'api.sqlite').as_posix()}"); repo.create_schema(); pid="00000000-0000-0000-0000-000000000001"
    with Session(repo.engine) as s: s.add(ProductORM(internal_id=pid,product_code="SP-API",company="HMS",part_name="Plate",quantity=100,unit="pcs",status="NEW")); s.commit()
    client=TestClient(build_stage2_api(Stage2Service(repo)))
    c=client.post("/api/v1/customers",json={"name":"HMS"},headers={"X-Actor":"api"}); assert c.status_code==200; customer=c.json()
    po=client.post("/api/v1/purchase-orders",json={"po_number":"PO-API","customer_id":customer["internal_id"],"po_date":"2026-08-01"}); assert po.status_code==200
    line=client.post(f"/api/v1/purchase-orders/{po.json()['internal_id']}/lines",json={"product_id":pid,"line_number":1,"ordered_quantity":100,"unit":"pcs"}); assert line.status_code==200
    lid=line.json()["internal_id"]
    assert client.post(f"/api/v1/purchase-order-lines/{lid}/delivery-schedules?ordered_quantity=100",json={"planned_date":"2026-08-20","planned_quantity":50}).status_code==200
    run=client.post("/api/v1/production-runs",json={"po_line_id":lid,"product_id":pid,"ordered_quantity":100,"planned_quantity":50}); assert run.status_code==200
    assert client.get("/api/v1/production-runs",params={"po_line_id":lid}).json()["items"]
