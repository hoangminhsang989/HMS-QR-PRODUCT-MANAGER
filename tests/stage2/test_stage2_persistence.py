from pathlib import Path
from datetime import date, datetime, timezone
from uuid import UUID

from packages.application.stage2_service import Stage2Service
from packages.domain.product import Product, ProductStatus
from packages.domain.stage2 import Stage2ValidationError
from packages.persistence.sqlalchemy_product_repository import SqlAlchemyProductRepository
from packages.persistence.sqlalchemy_repository import Stage2Repository


def test_sqlalchemy_sqlite_relationships_and_overallocation(tmp_path: Path):
    repo = Stage2Repository(f"sqlite:///{(tmp_path / 'stage2.sqlite').as_posix()}")
    repo.create_schema()
    product_id = "00000000-0000-0000-0000-000000000001"
    now = datetime.now(timezone.utc)
    SqlAlchemyProductRepository(repo.database).create(Product(
        internal_id=UUID(product_id), product_code="SP-1", company="HMS",
        part_name="Plate", quantity=100, unit="pcs", material=None, requester=None,
        surface_treatment=None, outsourced=False, size=None, notes=None,
        delivery_schedule=None, status=ProductStatus.NEW, created_at=now,
        updated_at=now, created_by="seed", updated_by="seed",
    ))
    svc=Stage2Service(repo); customer=svc.create_customer(actor="u",name="HMS")
    po=svc.create_po(actor="u",po_number="PO-1",customer_id=customer.internal_id,po_date=date(2026,8,1))
    line=svc.add_line(po_id=po.internal_id,product_id=product_id,line_number=1,ordered_quantity=100,unit="pcs")
    svc.add_delivery(po_line_id=line.internal_id,ordered_quantity=100,planned_date=date(2026,8,20),planned_quantity=60)
    svc.create_run(actor="u",run_code="RUN-1",po_line_id=line.internal_id,product_id=product_id,ordered_quantity=100,planned_quantity=40)
    try:
        svc.add_delivery(po_line_id=line.internal_id,ordered_quantity=100,planned_date=date(2026,8,21),planned_quantity=50)
    except Stage2ValidationError: pass
    else: raise AssertionError("delivery overallocation accepted")
    delivery = svc.list_deliveries(line.internal_id)[0]
    try:
        svc.update_delivery(__import__('dataclasses').replace(delivery, planned_quantity=110), ordered_quantity=100)
    except Stage2ValidationError:
        pass
    else:
        raise AssertionError("delivery update over-allocation accepted")
    assert len(svc.list_lines(po.internal_id)) == 1 and len(svc.list_runs(po_line_id=line.internal_id)) == 1
    run = svc.list_runs(po_line_id=line.internal_id)[0]
    try:
        svc.update_run(run.update(actor="u", planned_quantity=110), ordered_quantity=100)
    except Stage2ValidationError:
        pass
    else:
        raise AssertionError("run update over-allocation accepted")
    wrong_product = "00000000-0000-0000-0000-000000000002"
    try:
        svc.create_run(actor="u", po_line_id=line.internal_id, product_id=wrong_product, ordered_quantity=100, planned_quantity=1)
    except Stage2ValidationError:
        pass
    else:
        raise AssertionError("wrong Product/PO Line relation accepted")
